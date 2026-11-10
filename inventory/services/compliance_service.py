import hashlib
import html
import logging
import math
import re
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any, Literal, Optional

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.utils import timezone
from django.utils.translation import get_language
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from inventory.models import (
    ComplianceStage,
    ComplianceVerdict,
    MarketplaceSite,
    PolicyClause,
    PolicySeverity,
)

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = getattr(settings, "GEMINI_EMBEDDING_MODEL_NAME", "text-embedding-004")
DEFAULT_EXTRACTION_MODEL = "gemini-2.5-flash"
LOCAL_EMBEDDING_DIMS = 96


class ExtractedClauseSchema(BaseModel):
    code_suffix: str = Field(description="Short alphanumeric suffix for clause code, e.g. 901")
    category: str = Field(description="Policy domain category, e.g. Prohibited Goods, Hygiene, Counterfeit")
    severity: Literal["critical", "high", "medium"] = Field(description="Violation severity")
    title_es: str = Field(description="Concise Spanish title")
    title_en: str = Field(description="Concise English title")
    description_es: str = Field(description="Concise Spanish summary of the rule")
    description_en: str = Field(description="Concise English summary of the rule")
    hard_block_keywords: list[str] = Field(
        default_factory=list,
        description="Up to 10 lowercase trigger words/phrases in Spanish and English",
    )


class ExtractedPolicyClausesSchema(BaseModel):
    clauses: list[ExtractedClauseSchema] = Field(default_factory=list)


class _HTMLTextExtractor(HTMLParser):
    """Lightweight HTML-to-text parser stripping script/style/noscript blocks."""

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag.lower() in {"p", "br", "li", "div", "h1", "h2", "h3", "h4", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self._chunks.append(data)

    def get_text(self) -> str:
        joined = html.unescape(" ".join(self._chunks))
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in joined.splitlines()]
        return "\n".join(line for line in lines if line)


DEFAULT_POLICY_URL_MAP: dict[str, str] = {
    "wallapop": "https://ayuda.wallapop.com/hc/es-es/articles/360001796298",
    "vinted": "https://www.vinted.es/catalog-rules",
    "ebay": "https://www.ebay.es/help/policies/prohibited-restricted-items/prohibited-restricted-items?id=4207",
    "milanuncios": "https://www.milanuncios.com/condiciones-de-uso/",
}

DEFAULT_POLICY_CLAUSES_SEED: tuple[dict[str, Any], ...] = (
    {
        "code": "GLB-101",
        "site_slug": None,
        "category": "Weapons & Tactical",
        "severity": PolicySeverity.CRITICAL,
        "title_es": "Armas de fuego, munición, airsoft y armas blancas prohibidas",
        "title_en": "Firearms, Ammunition, Airsoft & Prohibited Blades",
        "description_es": (
            "Se prohíbe la venta de armas de fuego, piezas esenciales, munición, pistolas de aire "
            "comprimido o airsoft, táseres, sprays de pimienta y armas blancas prohibidas."
        ),
        "description_en": (
            "Sale of firearms, essential gun parts, ammunition, airsoft/pellet guns, tasers, "
            "pepper sprays, and prohibited switchblades or knuckles is strictly forbidden."
        ),
        "hard_block_keywords": [
            "pistola", "arma de fuego", "armas", "municion", "airsoft", "navaja automatica",
            "puno americano", "taser", "spray pimienta", "escopeta", "rifle",
            "firearm", "ammunition", "switchblade", "brass knuckles", "pepper spray", "handgun",
        ],
    },
    {
        "code": "GLB-102",
        "site_slug": None,
        "category": "Medical & Substances",
        "severity": PolicySeverity.CRITICAL,
        "title_es": "Medicamentos con receta, fármacos y suplementos regulados",
        "title_en": "Prescription Medicines, Drugs & Regulated Supplements",
        "description_es": (
            "Está prohibida la venta de medicamentos sujetos a prescripción médica, fármacos de farmacia, "
            "esteroides anabolizantes, dispositivos médicos invasivos y suplementos no autorizados."
        ),
        "description_en": (
            "Selling prescription medications, pharmacy drugs, anabolic steroids, invasive medical devices, "
            "and unauthorized therapeutic supplements is prohibited."
        ),
        "hard_block_keywords": [
            "medicamento", "receta medica", "antibiotico", "anabolizante", "esteroides",
            "viagra", "cialis", "insulina", "jeringuilla", "farmaco",
            "prescription", "antibiotic", "steroids", "pharmacy drug",
        ],
    },
    {
        "code": "GLB-103",
        "site_slug": None,
        "category": "Counterfeit & IP",
        "severity": PolicySeverity.CRITICAL,
        "title_es": "Artículos falsificados, réplicas o infracción de propiedad intelectual",
        "title_en": "Counterfeit Goods, Replicas & IP Infringement",
        "description_es": (
            "Prohibido anunciar falsificaciones, réplicas, imitaciones no oficiales o productos que vulneren "
            "derechos de marca registrada o propiedad intelectual."
        ),
        "description_en": (
            "Listing counterfeit items, replicas, unofficial knockoffs, or products infringing registered "
            "trademarks or copyrights is prohibited."
        ),
        "hard_block_keywords": [
            "replica", "imitacion", "falsificacion", "falso", "clon exacto", "calidad 1:1",
            "aaa+", "bootleg", "pirata", "counterfeit", "fake", "knockoff", "exact replica",
        ],
    },
    {
        "code": "GLB-104",
        "site_slug": None,
        "category": "Deceptive Copy / Health Claims",
        "severity": PolicySeverity.MEDIUM,
        "title_es": "Afirmaciones terapéuticas no verificadas y abuso de marcas (SEO stuffing)",
        "title_en": "Unverified Therapeutic Claims & Brand Keyword Stuffing",
        "description_es": (
            "Las descripciones no pueden prometer curas médicas o tratamientos terapéuticos ni incluir "
            "marcas ajenas en el texto ('tipo Zara', 'estilo Rolex') para manipular búsquedas."
        ),
        "description_en": (
            "Listing copy must not make unverified medical cure claims or stuff unrelated competitor "
            "brand names for search manipulation."
        ),
        "hard_block_keywords": [
            "cura el dolor", "cura enfermedades", "milagroso", "tratamiento medico",
            "elimina la artritis", "tipo zara", "estilo rolex", "como gucci",
            "cures pain", "medical cure", "miracle cure", "arthritis relief",
        ],
    },
    {
        "code": "GLB-105",
        "site_slug": None,
        "category": "Hazardous & Recalled",
        "severity": PolicySeverity.HIGH,
        "title_es": "Baterías dañadas/hinchadas, materiales inflamables y productos retirados",
        "title_en": "Damaged/Swollen Lithium Batteries, Hazardous & Recalled Goods",
        "description_es": (
            "No se permiten baterías de litio hinchadas o dañadas, gases inflamables, bombonas a presión, "
            "pirotecnia ni artículos sujetos a retirada de seguridad."
        ),
        "description_en": (
            "Swollen or damaged lithium batteries, flammable gases, pressurized cylinders, fireworks, "
            "and recalled safety-hazard products are prohibited."
        ),
        "hard_block_keywords": [
            "bateria hinchada", "bateria danada", "inflamable", "explosivo", "gas butano",
            "bombona", "pirotecnia", "retirado del mercado", "amianto",
            "swollen battery", "damaged battery", "flammable", "explosive", "recalled product",
        ],
    },
    {
        "code": "GLB-106",
        "site_slug": None,
        "category": "Digital Piracy & Security Tools",
        "severity": PolicySeverity.HIGH,
        "title_es": "Cuentas digitales, software pirata, decodificadores IPTV y ganzúas",
        "title_en": "Digital Accounts, Pirated Software & Lockpicking Tools",
        "description_es": (
            "Prohibida la venta de cuentas de streaming compartidas, licencias pirata, dispositivos de "
            "elusión anticopia y herramientas de cerrajería no profesionales como ganzúas."
        ),
        "description_en": (
            "Shared streaming accounts, pirated software keys, circumvention modchips, and "
            "lockpicking tools are prohibited."
        ),
        "hard_block_keywords": [
            "cuenta netflix", "cuenta spotify", "licencia pirateada", "iptv pirata",
            "modchip", "ganzua", "pirated software", "cracked license", "lockpick", "streaming account",
        ],
    },
    {
        "code": "GLB-107",
        "site_slug": None,
        "category": "Personal Data & Official IDs",
        "severity": PolicySeverity.HIGH,
        "title_es": "Documentos oficiales, datos personales y tarjetas financieras",
        "title_en": "Official IDs, Personal Data & Financial Cards",
        "description_es": (
            "Prohibido vender documentos de identidad, pasaportes, permisos de conducir, tarjetas "
            "bancarias o soportes con datos personales sin borrar."
        ),
        "description_en": (
            "Selling official ID cards, passports, driver licenses, credit/debit cards, or devices "
            "with unwiped personal data is strictly prohibited."
        ),
        "hard_block_keywords": [
            "pasaporte", "carnet de conducir", "tarjeta de credito", "datos bancarios",
            "passport", "driver license", "credit card", "bank card",
        ],
    },
    {
        "code": "VT-201",
        "site_slug": "vinted",
        "category": "Hygiene & Cosmetics (Vinted)",
        "severity": PolicySeverity.HIGH,
        "title_es": "Vinted: Cosméticos o perfumes abiertos/usados e higiene personal",
        "title_en": "Vinted: Opened/Used Cosmetics, Perfumes & Hygiene Items",
        "description_es": (
            "En Vinted los perfumes, maquillajes y cosméticos deben ser nuevos y conservar su precinto "
            "original sin abrir; artículos de higiene usados están prohibidos."
        ),
        "description_en": (
            "Vinted requires cosmetics and perfumes to be brand new and factory sealed; "
            "opened or used personal hygiene products are prohibited."
        ),
        "hard_block_keywords": [
            "perfume empezado", "perfume abierto", "maquillaje usado", "cosmetico abierto",
            "crema usada", "ropa interior usada", "used makeup", "opened perfume",
            "opened cosmetic", "used underwear",
        ],
    },
    {
        "code": "VT-202",
        "site_slug": "vinted",
        "category": "Catalog Scope (Vinted)",
        "severity": PolicySeverity.MEDIUM,
        "title_es": "Vinted: Electrodomésticos, herramientas eléctricas y recambios de motor",
        "title_en": "Vinted: Appliances, Power Tools & Automotive Parts Restricted",
        "description_es": (
            "Las normas de catálogo de Vinted excluyen grandes electrodomésticos, herramientas eléctricas "
            "de bricolaje y recambios mecánicos de automóvil o motocicleta."
        ),
        "description_en": (
            "Vinted catalog rules restrict household appliances, electric power tools, "
            "and mechanical automotive or motorcycle replacement parts."
        ),
        "hard_block_keywords": [
            "lavadora", "frigorifico", "nevera", "freidora de aire", "microondas",
            "taladro", "radial", "amoladora", "motosierra", "neumatico", "llanta", "carburador",
            "washing machine", "fridge", "air fryer", "power drill", "angle grinder", "car tire",
        ],
    },
    {
        "code": "WP-301",
        "site_slug": "wallapop",
        "category": "Regulated Consumables (Wallapop)",
        "severity": PolicySeverity.HIGH,
        "title_es": "Wallapop: Tabaco, vapers, cigarrillos electrónicos y alcohol",
        "title_en": "Wallapop: Tobacco, Vapes, E-Cigarettes & Alcohol",
        "description_es": (
            "Wallapop prohíbe la publicación de tabaco, cigarrillos electrónicos, vapers, líquidos con "
            "nicotina, cachimbas/shishas y bebidas alcohólicas."
        ),
        "description_en": (
            "Wallapop prohibits tobacco, e-cigarettes, vapes, nicotine liquids, hookahs/shishas, "
            "and alcoholic beverages."
        ),
        "hard_block_keywords": [
            "vaper", "cigarrillo electronico", "e-liquid", "nicotina", "shisha", "cachimba",
            "tabaco", "botella de vino", "whisky", "licor",
            "vape", "e-cigarette", "nicotine", "tobacco", "alcohol bottle",
        ],
    },
    {
        "code": "EB-401",
        "site_slug": "ebay",
        "category": "Automotive Safety & OEM (eBay)",
        "severity": PolicySeverity.HIGH,
        "title_es": "eBay: Catalizadores usados, módulos de airbag y discos OEM",
        "title_en": "eBay: Used Catalytic Converters, Airbag Modules & OEM Software",
        "description_es": (
            "eBay restringe o prohíbe la venta de módulos airbag usados, catalizadores de desguace sin "
            "certificación y software OEM suelto sin el hardware original."
        ),
        "description_en": (
            "eBay restricts used airbag modules, uncertified catalytic converters, and standalone OEM "
            "software without accompanying original hardware."
        ),
        "hard_block_keywords": [
            "catalizador", "modulo airbag", "airbag usado", "disco oem", "windows oem",
            "catalytic converter", "airbag module", "oem recovery disc",
        ],
    },
    {
        "code": "ML-501",
        "site_slug": "milanuncios",
        "category": "Regulated Agro & Animals (Milanuncios)",
        "severity": PolicySeverity.MEDIUM,
        "title_es": "Milanuncios: Fitosanitarios profesionales, semillas protegidas y animales",
        "title_en": "Milanuncios: Regulated Agrochemicals, Seeds & Live Animals",
        "description_es": (
            "Milanuncios exige acreditación para fitosanitarios de uso profesional y prohíbe la venta "
            "irregular de animales de compañía o especies protegidas."
        ),
        "description_en": (
            "Milanuncios restricts professional agrochemicals without authorization and prohibits "
            "unregulated sales of pets or protected species."
        ),
        "hard_block_keywords": [
            "fitosanitario", "herbicida profesional", "pesticida", "cachorro", "mascota",
            "animal vivo", "pesticide", "herbicide", "live puppy", "live animal",
        ],
    },
)


def normalize_text(text: str) -> str:
    """Lowercase and strip diacritics for accent-insensitive Spanish/English matching."""
    raw = (text or "").strip().lower()
    nfkd = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _tokenize(text: str) -> list[str]:
    norm = normalize_text(text)
    return re.findall(r"[a-z0-9]{2,}", norm)


def compute_local_ngram_vector(text: str, dims: int = LOCAL_EMBEDDING_DIMS) -> list[float]:
    """
    Deterministic lightweight hashed char-trigram + word-token embedding vector.
    Provides fast (<1ms) offline/fallback semantic similarity in SQLite without external APIs.
    """
    norm = normalize_text(text)
    if not norm:
        return [0.0] * dims

    vec = [0.0] * dims
    tokens = _tokenize(norm)
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dims] += 2.0
        if len(tok) >= 4:
            for idx in range(len(tok) - 2):
                gram = tok[idx:idx + 3]
                gh = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16)
                vec[gh % dims] += 0.6

    magnitude = math.sqrt(sum(v * v for v in vec))
    if magnitude > 0:
        vec = [round(v / magnitude, 6) for v in vec]
    return vec


def compute_embedding_vector(text: str, use_api: bool = False) -> list[float]:
    """
    Computes an embedding vector for a policy clause or product text.
    Uses Gemini Embedding API only when `use_api=True` and `GEMINI_API_KEY` is configured;
    always falls back gracefully to deterministic local n-gram vectors.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return [0.0] * LOCAL_EMBEDDING_DIMS

    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if use_api and api_key.strip():
        try:
            client = genai.Client(api_key=api_key.strip())
            result = client.models.embed_content(
                model=EMBEDDING_MODEL_NAME,
                contents=clean_text,
            )
            embeddings = getattr(result, "embeddings", None)
            if embeddings and len(embeddings) > 0:
                values = list(getattr(embeddings[0], "values", []) or [])
                if values:
                    return [float(x) for x in values]
            single = getattr(result, "embedding", None)
            if single and getattr(single, "values", None):
                return [float(x) for x in single.values]
        except Exception as exc:
            logger.warning("Gemini embedding fallback to local vector: %s", exc)

    return compute_local_ngram_vector(clean_text)


def cosine_similarity(vec_a: list[float] | tuple[float, ...], vec_b: list[float] | tuple[float, ...]) -> float:
    """Computes cosine similarity in [0.0, 1.0] safely, returning 0.0 on empty or mismatched dimensions."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return max(0.0, min(1.0, round(dot / (norm_a * norm_b), 4)))


def ensure_default_policy_clauses(use_api_embeddings: bool = False) -> int:
    """
    Idempotently seeds curated global and per-platform policy clauses (Wallapop, Vinted, eBay, Milanuncios).
    Also ensures default `policy_url` values are populated on known MarketplaceSite entries if blank.
    """
    sites_by_slug = {s.slug: s for s in MarketplaceSite.objects.all()}
    for slug, url in DEFAULT_POLICY_URL_MAP.items():
        site = sites_by_slug.get(slug)
        if site and not (site.policy_url or "").strip():
            site.policy_url = url
            site.save(update_fields=["policy_url", "updated_at"])

    created_count = 0
    for item in DEFAULT_POLICY_CLAUSES_SEED:
        site_obj = sites_by_slug.get(item["site_slug"]) if item["site_slug"] else None
        seed_text = (
            f"{item['title_es']} {item['title_en']} "
            f"{item['description_es']} {item['description_en']} "
            f"{' '.join(item['hard_block_keywords'])}"
        )
        defaults = {
            "site": site_obj,
            "category": item["category"],
            "severity": item["severity"],
            "title_es": item["title_es"],
            "title_en": item["title_en"],
            "description_es": item["description_es"],
            "description_en": item["description_en"],
            "hard_block_keywords": list(item["hard_block_keywords"]),
            "embedding_vector": compute_embedding_vector(seed_text, use_api=use_api_embeddings),
            "is_active": True,
        }
        obj, created = PolicyClause.objects.get_or_create(code=item["code"], defaults=defaults)
        if created:
            created_count += 1
        elif not obj.embedding_vector:
            obj.embedding_vector = compute_embedding_vector(seed_text, use_api=use_api_embeddings)
            obj.save(update_fields=["embedding_vector", "updated_at"])
    return created_count


def _match_keyword(normalized_haystack: str, keyword: str) -> bool:
    kw = normalize_text(keyword)
    if not kw:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])"
    return bool(re.search(pattern, normalized_haystack))


def _estimate_naive_baseline_tokens(clauses: list[PolicyClause], sites: list[MarketplaceSite]) -> int:
    raw_policy_chars = sum(len((s.policy_raw_text or "").strip()) for s in sites)
    clause_chars = sum(
        len(c.title_es or "") + len(c.description_es or "") + len(c.title_en or "") + len(c.description_en or "")
        for c in clauses
    )
    estimated = (raw_policy_chars + clause_chars * 4) // 4
    return max(12000, estimated)


def _severity_score(severity: str, is_global: bool) -> int:
    if severity == PolicySeverity.CRITICAL:
        return 92 if is_global else 82
    if severity == PolicySeverity.HIGH:
        return 75 if is_global else 60
    return 48 if is_global else 40


def build_platform_matrix(
    matched_clauses: list[dict[str, Any]],
    sites: Optional[list[MarketplaceSite]] = None,
) -> dict[str, dict[str, Any]]:
    """
    Constructs the per-platform compatibility matrix (`rapido-pack` Storefront + active MarketplaceSites).
    Global matches propagate to every platform; site-specific matches flag only that specific platform.
    """
    if sites is None:
        try:
            sites = list(MarketplaceSite.objects.filter(is_active=True).order_by("order", "name"))
        except (OperationalError, ProgrammingError):
            sites = []

    platforms: list[tuple[str, str]] = [("rapido-pack", "Rápido Pack")]
    seen_slugs = {"rapido-pack"}
    for site in sites:
        if site.slug and site.slug not in seen_slugs:
            platforms.append((site.slug, site.name))
            seen_slugs.add(site.slug)

    matrix: dict[str, dict[str, Any]] = {}
    for slug, name in platforms:
        matrix[slug] = {
            "slug": slug,
            "name": name,
            "status": ComplianceVerdict.APPROVED,
            "clauses": [],
        }

    for clause in matched_clauses:
        clause_code = clause.get("code", "")
        severity = clause.get("severity", PolicySeverity.MEDIUM)
        site_slug = clause.get("site_slug") or ""

        if not site_slug:
            target_status = (
                ComplianceVerdict.REJECTED
                if severity == PolicySeverity.CRITICAL
                else ComplianceVerdict.MANUAL_REVIEW
            )
            for slug, entry in matrix.items():
                if clause_code and clause_code not in entry["clauses"]:
                    entry["clauses"].append(clause_code)
                if entry["status"] != ComplianceVerdict.REJECTED:
                    entry["status"] = target_status
        else:
            if site_slug not in matrix:
                matrix[site_slug] = {
                    "slug": site_slug,
                    "name": clause.get("site_name") or site_slug.title(),
                    "status": ComplianceVerdict.APPROVED,
                    "clauses": [],
                }
            entry = matrix[site_slug]
            if clause_code and clause_code not in entry["clauses"]:
                entry["clauses"].append(clause_code)
            target_status = (
                ComplianceVerdict.REJECTED
                if severity == PolicySeverity.CRITICAL
                else ComplianceVerdict.MANUAL_REVIEW
            )
            if entry["status"] != ComplianceVerdict.REJECTED:
                entry["status"] = target_status

    return matrix


def _build_telemetry(top_k_sent: int, tokens_used: int, naive_baseline_tokens: int) -> dict[str, Any]:
    saved_pct = 0.0
    if naive_baseline_tokens > 0:
        saved_pct = max(0.0, round((1.0 - (tokens_used / naive_baseline_tokens)) * 100.0, 1))
    return {
        "top_k_clauses_sent": top_k_sent,
        "tokens_used": tokens_used,
        "naive_baseline_tokens": naive_baseline_tokens,
        "tokens_saved_percent": saved_pct,
    }


def evaluate_stage1_local(
    *,
    title: str = "",
    description: str = "",
    raw_note: str = "",
    category_name: str = "",
    language: Optional[str] = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """
    Stage 1 fast local policy filter (<5ms, 0 LLM tokens).
    Scans product text against `hard_block_keywords` and ranks `PolicyClause` items via local cosine similarity.
    Returns verdict, risk_score, stage, top_clauses (for Stage 2 prompt injection), and full structured report.
    """
    lang = (language or get_language() or "es").lower()
    combined_text = " ".join(part.strip() for part in (title, description, raw_note, category_name) if part and part.strip())
    norm_text = normalize_text(combined_text)

    try:
        if not PolicyClause.objects.exists():
            ensure_default_policy_clauses(use_api_embeddings=False)
        clauses = list(PolicyClause.objects.filter(is_active=True).select_related("site").order_by("code"))
        sites = list(MarketplaceSite.objects.filter(is_active=True).order_by("order", "name"))
    except (OperationalError, ProgrammingError):
        clauses = []
        sites = []

    naive_baseline = _estimate_naive_baseline_tokens(clauses, sites)

    if not norm_text or not clauses:
        matrix = build_platform_matrix([], sites=sites)
        return {
            "verdict": ComplianceVerdict.APPROVED,
            "risk_score": 0,
            "stage": ComplianceStage.STAGE_1_SAFE,
            "top_clauses": [],
            "report": {
                "summary": "No prohibited policy keywords or risk signals detected.",
                "matched_clauses": [],
                "sanitized_actions": [],
                "platform_matrix": matrix,
                "telemetry": _build_telemetry(top_k_sent=0, tokens_used=0, naive_baseline_tokens=naive_baseline),
            },
        }

    product_vec = compute_local_ngram_vector(combined_text)
    scored_clauses: list[tuple[float, PolicyClause, list[str], float]] = []

    for clause in clauses:
        matched_kws = [kw for kw in (clause.hard_block_keywords or []) if _match_keyword(norm_text, kw)]
        clause_text = (
            f"{clause.title_es} {clause.title_en} "
            f"{clause.description_es} {clause.description_en} "
            f"{' '.join(clause.hard_block_keywords or [])}"
        )
        clause_local_vec = compute_local_ngram_vector(clause_text)
        sim = cosine_similarity(product_vec, clause_local_vec)
        if clause.embedding_vector and len(clause.embedding_vector) == len(product_vec):
            sim = max(sim, cosine_similarity(product_vec, clause.embedding_vector))

        rank_score = sim + (1.0 if matched_kws else 0.0) + (0.15 * len(matched_kws))
        scored_clauses.append((rank_score, clause, matched_kws, sim))

    scored_clauses.sort(key=lambda item: item[0], reverse=True)
    top_entries = scored_clauses[:max(1, top_k)]
    top_clauses = [entry[1] for entry in top_entries]

    matched_clauses_data: list[dict[str, Any]] = []
    max_risk = 0
    has_global_critical = False
    has_lexical_hit = False

    for _rank, clause, matched_kws, sim in scored_clauses:
        if matched_kws:
            has_lexical_hit = True
            is_global = clause.site_id is None
            risk = _severity_score(clause.severity, is_global=is_global)
            max_risk = max(max_risk, risk)
            if is_global and clause.severity == PolicySeverity.CRITICAL:
                has_global_critical = True

            matched_clauses_data.append(
                {
                    "code": clause.code,
                    "site_slug": clause.site.slug if clause.site_id and clause.site else "",
                    "site_name": clause.site.name if clause.site_id and clause.site else "Rápido Pack / Global",
                    "title": clause.get_localized_title(lang),
                    "title_es": clause.title_es,
                    "title_en": clause.title_en,
                    "severity": clause.severity,
                    "similarity": round(sim, 3),
                    "matched_keywords": matched_kws,
                    "excerpt": ", ".join(matched_kws),
                    "explanation": clause.get_localized_description(lang),
                    "explanation_es": clause.description_es,
                    "explanation_en": clause.description_en,
                }
            )

    if has_global_critical:
        verdict = ComplianceVerdict.REJECTED
    elif matched_clauses_data:
        verdict = ComplianceVerdict.MANUAL_REVIEW
    else:
        verdict = ComplianceVerdict.APPROVED
        top_sim = top_entries[0][3] if top_entries else 0.0
        max_risk = min(20, int(round(top_sim * 25)))

    stage = ComplianceStage.STAGE_1_LEXICAL if has_lexical_hit else ComplianceStage.STAGE_1_SAFE
    matrix = build_platform_matrix(matched_clauses_data, sites=sites)

    if matched_clauses_data:
        summary = "; ".join(
            f"[{m['code']}] {m['title']} ({m['excerpt']})" for m in matched_clauses_data[:3]
        )
    else:
        summary = "Stage 1 clean pass — no prohibited keywords detected."

    return {
        "verdict": verdict,
        "risk_score": max_risk,
        "stage": stage,
        "top_clauses": top_clauses,
        "report": {
            "summary": summary,
            "matched_clauses": matched_clauses_data,
            "sanitized_actions": [],
            "platform_matrix": matrix,
            "telemetry": _build_telemetry(top_k_sent=0, tokens_used=0, naive_baseline_tokens=naive_baseline),
        },
    }


def evaluate_stage1_local_for_product(product: Any, language: Optional[str] = None, top_k: int = 3) -> dict[str, Any]:
    """Convenience wrapper running Stage 1 local compliance on a Product model instance."""
    cat_name = ""
    if getattr(product, "category_id", None) and getattr(product, "category", None):
        cat_name = product.category.name or ""
    return evaluate_stage1_local(
        title=getattr(product, "ai_title", "") or "",
        description=getattr(product, "ai_description", "") or "",
        raw_note=getattr(product, "raw_note", "") or "",
        category_name=cat_name,
        language=language,
        top_k=top_k,
    )


def format_top_clauses_prompt_block(clauses: list[PolicyClause], language: str = "es") -> str:
    """
    Formats ONLY the top-K (default 3) candidate clauses into a compact ~150-token prompt snippet
    for Stage 2 piggybacking, avoiding full Terms & Conditions upload.
    """
    if not clauses:
        return ""
    is_es = str(language).lower().startswith("es")
    header = (
        "REGLAS DE POLÍTICA RELEVANTES (TOP-3 CLAUSEGUARD):"
        if is_es
        else "RELEVANT POLICY CLAUSES (TOP-3 CLAUSEGUARD):"
    )
    lines = [header]
    for clause in clauses:
        scope = clause.site.name if clause.site_id and clause.site else ("Global" if is_es else "Global")
        title = clause.title_es if is_es else (clause.title_en or clause.title_es)
        desc = clause.description_es if is_es else (clause.description_en or clause.description_es)
        lines.append(f"- [{clause.code} | {scope} | {clause.severity}] {title}: {desc}")
    return "\n".join(lines)


def merge_stage2_compliance_result(
    *,
    stage1_result: dict[str, Any],
    ai_verdict: Optional[str] = None,
    ai_risk_score: Optional[int] = None,
    violated_clause_codes: Optional[list[str]] = None,
    ai_explanation: str = "",
    sanitized_note: str = "",
    stage: str = ComplianceStage.STAGE_2_PIGGYBACK,
    tokens_used: int = 150,
    language: Optional[str] = None,
) -> dict[str, Any]:
    """
    Merges Stage 1 deterministic hits with Stage 2 Gemini adjudication.
    Never downgrades a deterministic Stage 1 CRITICAL violation to safe.
    """
    lang = (language or get_language() or "es").lower()
    matched_by_code: dict[str, dict[str, Any]] = {
        m["code"]: dict(m) for m in (stage1_result.get("report", {}).get("matched_clauses") or [])
    }

    codes = [str(c).strip() for c in (violated_clause_codes or []) if str(c).strip()]
    if codes:
        clauses_map = {
            c.code: c
            for c in PolicyClause.objects.filter(code__in=codes).select_related("site")
        }
        for code in codes:
            if code in matched_by_code:
                if ai_explanation:
                    matched_by_code[code]["explanation"] = ai_explanation
                    matched_by_code[code].pop("explanation_es", None)
                    matched_by_code[code].pop("explanation_en", None)
            elif code in clauses_map:
                clause = clauses_map[code]
                entry = {
                    "code": clause.code,
                    "site_slug": clause.site.slug if clause.site_id and clause.site else "",
                    "site_name": clause.site.name if clause.site_id and clause.site else "Rápido Pack / Global",
                    "title": clause.get_localized_title(lang),
                    "title_es": clause.title_es,
                    "title_en": clause.title_en,
                    "severity": clause.severity,
                    "similarity": 1.0,
                    "matched_keywords": [],
                    "excerpt": "AI multimodal check",
                    "explanation": ai_explanation or clause.get_localized_description(lang),
                }
                if not ai_explanation:
                    entry["explanation_es"] = clause.description_es
                    entry["explanation_en"] = clause.description_en
                matched_by_code[code] = entry

    merged_matched = list(matched_by_code.values())

    valid_verdicts = {choice[0] for choice in ComplianceVerdict.choices}
    clean_ai_verdict = (ai_verdict or "").strip().lower()
    if clean_ai_verdict not in valid_verdicts:
        clean_ai_verdict = stage1_result.get("verdict", ComplianceVerdict.APPROVED)

    verdict_rank = {
        ComplianceVerdict.APPROVED: 0,
        ComplianceVerdict.MANUAL_REVIEW: 1,
        ComplianceVerdict.REJECTED: 2,
    }
    stage1_verdict = stage1_result.get("verdict", ComplianceVerdict.APPROVED)
    # Deterministic hard-block takes precedence if stricter; otherwise respect AI risk detection
    final_verdict = (
        stage1_verdict
        if verdict_rank.get(stage1_verdict, 0) > verdict_rank.get(clean_ai_verdict, 0)
        else clean_ai_verdict
    )
    if merged_matched and final_verdict == ComplianceVerdict.APPROVED:
        final_verdict = ComplianceVerdict.MANUAL_REVIEW

    stage1_risk = int(stage1_result.get("risk_score", 0) or 0)
    parsed_ai_risk = 0
    if ai_risk_score is not None:
        try:
            parsed_ai_risk = max(0, min(100, int(ai_risk_score)))
        except (ValueError, TypeError):
            parsed_ai_risk = 0
    final_risk = max(stage1_risk, parsed_ai_risk)

    sanitized_actions = list(stage1_result.get("report", {}).get("sanitized_actions") or [])
    if sanitized_note and sanitized_note.strip():
        sanitized_actions.append(sanitized_note.strip())

    matrix = build_platform_matrix(merged_matched)
    top_k_sent = len(stage1_result.get("top_clauses") or [])
    naive_baseline = (
        stage1_result.get("report", {})
        .get("telemetry", {})
        .get("naive_baseline_tokens", 12000)
    )

    summary = ai_explanation.strip() if ai_explanation and ai_explanation.strip() else (
        stage1_result.get("report", {}).get("summary", "")
    )

    return {
        "verdict": final_verdict,
        "risk_score": final_risk,
        "stage": stage,
        "report": {
            "summary": summary,
            "matched_clauses": merged_matched,
            "sanitized_actions": sanitized_actions,
            "platform_matrix": matrix,
            "telemetry": _build_telemetry(
                top_k_sent=top_k_sent,
                tokens_used=max(0, int(tokens_used)),
                naive_baseline_tokens=naive_baseline,
            ),
        },
    }


class TargetedComplianceCheckSchema(BaseModel):
    compliance_verdict: Literal["approved", "manual_review", "rejected"]
    compliance_risk_score: int = Field(ge=0, le=100)
    violated_clause_codes: list[str] = Field(default_factory=list)
    explanation: str = Field(default="")


def verify_product_compliance_ai(product: Any, language: Optional[str] = None) -> dict[str, Any]:
    """
    On-demand targeted Stage 1 -> Stage 2 verification for an existing product.
    Sends ONLY the top-3 matched clauses (~250 tokens) to Gemini without modifying `ai_title` or `ai_description`.
    Falls back cleanly to Stage 1 if GEMINI_API_KEY is unconfigured or API fails.
    """
    lang = (language or get_language() or "es").lower()
    stage1 = evaluate_stage1_local_for_product(product, language=lang, top_k=3)
    top_clauses = stage1.get("top_clauses") or []
    clauses_block = format_top_clauses_prompt_block(top_clauses, language=lang)

    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key.strip() or not top_clauses:
        return stage1

    is_es = lang.startswith("es")
    prompt = (
        (
            "Evalúa si este producto de segunda mano infringe alguna de las siguientes 3 cláusulas de política. "
            "Responde en español.\n\n"
            if is_es
            else "Evaluate whether this secondhand product violates any of the following 3 policy clauses. "
            "Respond in English.\n\n"
        )
        + f"TITLE: {product.ai_title or ''}\n"
        + f"DESCRIPTION: {product.ai_description or ''}\n"
        + f"FIELD NOTES: {product.raw_note or ''}\n\n"
        + clauses_block
    )

    try:
        client = genai.Client(api_key=api_key.strip())
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TargetedComplianceCheckSchema,
            temperature=0.1,
        )
        response = client.models.generate_content(
            model=DEFAULT_EXTRACTION_MODEL,
            contents=[prompt],
            config=config,
        )
        usage = getattr(response, "usage_metadata", None)
        tokens_used = int(getattr(usage, "total_token_count", 0) or 0) or max(120, len(prompt) // 4 + 60)

        parsed = getattr(response, "parsed", None)
        if parsed:
            return merge_stage2_compliance_result(
                stage1_result=stage1,
                ai_verdict=getattr(parsed, "compliance_verdict", None),
                ai_risk_score=getattr(parsed, "compliance_risk_score", 0),
                violated_clause_codes=list(getattr(parsed, "violated_clause_codes", []) or []),
                ai_explanation=getattr(parsed, "explanation", ""),
                stage=ComplianceStage.STAGE_2_TARGETED,
                tokens_used=tokens_used,
                language=lang,
            )
    except Exception as exc:
        logger.warning("Targeted Stage 2 compliance check fallback to Stage 1: %s", exc)

    return stage1


def fetch_policy_text_from_url(url: str, timeout: float = 8.0) -> tuple[str, Optional[str]]:
    """
    Attempts to fetch and extract readable text from a marketplace Terms & Conditions URL.
    Returns (cleaned_text, error_message). Never raises on network or HTTP anti-bot failures.
    """
    clean_url = (url or "").strip()
    if not clean_url:
        return "", "No policy URL configured."

    req = urllib.request.Request(
        clean_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status >= 400:
                return "", f"HTTP {status} returned by {clean_url}"
            raw_bytes = resp.read(512_000)
            charset = resp.headers.get_content_charset() or "utf-8"
            raw_html = raw_bytes.decode(charset, errors="replace")
            extractor = _HTMLTextExtractor()
            extractor.feed(raw_html)
            extracted = extractor.get_text()
            if len(extracted) < 80:
                return "", f"Insufficient readable policy text extracted from {clean_url}"
            return extracted, None
    except urllib.error.HTTPError as exc:
        return "", f"HTTP {exc.code} blocked/failed fetching {clean_url}"
    except Exception as exc:
        return "", f"Failed fetching {clean_url}: {exc}"


def sync_site_policy(
    site: MarketplaceSite,
    *,
    force: bool = False,
    dry_run: bool = False,
    use_api: bool = True,
) -> dict[str, Any]:
    """
    Hybrid URL/Raw-Text policy synchronization for a MarketplaceSite.
    1. Tries fetching `site.policy_url`; falls back to `site.policy_raw_text` if blocked/empty.
    2. Computes SHA-256 content hash and skips AI/embedding indexing if unchanged (0 tokens).
    3. When changed, extracts atomic PolicyClause rows via Gemini (or refreshes local vectors offline).
    """
    ensure_default_policy_clauses(use_api_embeddings=False)

    fetched_text = ""
    fetch_error = None
    source_used = ""

    if (site.policy_url or "").strip():
        fetched_text, fetch_error = fetch_policy_text_from_url(site.policy_url)
        if fetched_text:
            source_used = "url"

    if not fetched_text and (site.policy_raw_text or "").strip():
        fetched_text = site.policy_raw_text.strip()
        source_used = "raw_text"

    if not fetched_text:
        return {
            "site": site.slug,
            "status": "skipped_no_content",
            "source": "none",
            "error": fetch_error or "No policy URL content or raw fallback text available.",
            "clauses_updated": 0,
        }

    content_hash = hashlib.sha256(fetched_text.encode("utf-8")).hexdigest()
    if not force and site.policy_content_hash == content_hash:
        return {
            "site": site.slug,
            "status": "unchanged",
            "source": source_used,
            "hash": content_hash,
            "clauses_updated": 0,
        }

    if dry_run:
        return {
            "site": site.slug,
            "status": "would_sync",
            "source": source_used,
            "hash": content_hash,
            "clauses_updated": 0,
        }

    clauses_updated = 0
    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    extracted_clauses: list[ExtractedClauseSchema] = []

    if use_api and api_key.strip():
        try:
            client = genai.Client(api_key=api_key.strip())
            snippet = fetched_text[:18000]
            prompt = (
                f"Extract up to 8 concise prohibited/restricted item rules from {site.name}'s Terms & Conditions.\n"
                "Provide Spanish and English titles/descriptions and lowercase trigger keywords.\n\n"
                f"POLICY TEXT:\n{snippet}"
            )
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ExtractedPolicyClausesSchema,
                temperature=0.1,
            )
            response = client.models.generate_content(
                model=DEFAULT_EXTRACTION_MODEL,
                contents=[prompt],
                config=config,
            )
            parsed = getattr(response, "parsed", None)
            if parsed and getattr(parsed, "clauses", None):
                extracted_clauses = list(parsed.clauses)
        except Exception as exc:
            logger.warning("Gemini policy clause extraction fallback for %s: %s", site.slug, exc)

    site_prefix = re.sub(r"[^A-Z0-9]", "", (site.slug or "SITE").upper())[:4] or "SITE"
    for idx, item in enumerate(extracted_clauses, start=1):
        suffix = re.sub(r"[^A-Z0-9]", "", (item.code_suffix or str(900 + idx)).upper())[:12] or str(900 + idx)
        code = f"{site_prefix}-{suffix}"
        clause_text = (
            f"{item.title_es} {item.title_en} {item.description_es} {item.description_en} "
            f"{' '.join(item.hard_block_keywords or [])}"
        )
        PolicyClause.objects.update_or_create(
            code=code,
            defaults={
                "site": site,
                "category": (item.category or "Platform Rule")[:80],
                "severity": item.severity,
                "title_es": (item.title_es or item.title_en)[:200],
                "title_en": (item.title_en or item.title_es)[:200],
                "description_es": item.description_es or item.description_en,
                "description_en": item.description_en or item.description_es,
                "hard_block_keywords": [str(k).strip().lower() for k in (item.hard_block_keywords or []) if str(k).strip()],
                "embedding_vector": compute_embedding_vector(clause_text, use_api=use_api),
                "is_active": True,
            },
        )
        clauses_updated += 1

    # Also ensure existing clauses for this site have up-to-date vectors
    for existing_clause in PolicyClause.objects.filter(site=site, is_active=True):
        if not existing_clause.embedding_vector or force:
            clause_text = (
                f"{existing_clause.title_es} {existing_clause.title_en} "
                f"{existing_clause.description_es} {existing_clause.description_en} "
                f"{' '.join(existing_clause.hard_block_keywords or [])}"
            )
            existing_clause.embedding_vector = compute_embedding_vector(clause_text, use_api=use_api)
            existing_clause.save(update_fields=["embedding_vector", "updated_at"])
            if not extracted_clauses:
                clauses_updated += 1

    site.policy_content_hash = content_hash
    site.policy_last_synced_at = timezone.now()
    if source_used == "url" and not (site.policy_raw_text or "").strip():
        site.policy_raw_text = fetched_text[:30000]
        site.save(update_fields=["policy_content_hash", "policy_last_synced_at", "policy_raw_text", "updated_at"])
    else:
        site.save(update_fields=["policy_content_hash", "policy_last_synced_at", "updated_at"])

    return {
        "site": site.slug,
        "status": "synced",
        "source": source_used,
        "hash": content_hash,
        "clauses_updated": clauses_updated,
        "fallback_error": fetch_error,
    }
