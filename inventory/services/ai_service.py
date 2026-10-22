import json
import logging
from typing import Dict, Literal, Optional, Tuple

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from inventory.models import OFFICIAL_CATEGORIES, ClarificationStatus, Product, ProductCondition

logger = logging.getLogger(__name__)

VALID_CATEGORY_SLUGS = {item[0] for item in OFFICIAL_CATEGORIES}
VALID_CONDITION_CODES = {choice[0] for choice in ProductCondition.choices}

OfficialCategorySlug = Literal[
    "motor-y-accesorios",
    "moda-y-accesorios",
    "tecnologia-y-electronica",
    "deporte-y-ocio",
    "bicicletas",
    "hogar-y-jardin",
    "electrodomesticos",
    "cine-libros-y-musica",
    "ninos-y-bebes",
    "coleccionismo",
    "construccion-y-reformas",
    "industria-y-agricultura",
]

OfficialConditionCode = Literal[
    "new_with_tags",
    "very_good",
    "good",
    "vintage",
]

DEFAULT_MODEL_NAME = "gemini-2.5-flash"
INTAKE_IDENTIFICATION_MODEL_NAME = getattr(settings, "GEMINI_INTAKE_MODEL_NAME", "gemini-flash-latest")
DEFAULT_TEMPERATURE = 0.3

DEFAULT_ES_INSTRUCTION = (
    "Eres un experto en reventa y comercialización de artículos de segunda mano y vintage. "
    "Analiza las fotos adjuntas y las notas de campo para redactar una publicación de marketplace (para Wallapop, Vinted, eBay).\n\n"
    "INSTRUCCIONES:\n"
    "- Idioma: Redacta el título y la descripción COMPLETAMENTE EN ESPAÑOL.\n"
    "- Título: Claro, conciso y rico en palabras clave (Marca, modelo, estilo principal, estado).\n"
    "- Descripción: Argumento de venta atractivo, detalles del artículo, evaluación del estado y mención explícita de cualquier defecto o desgaste observado en las fotos o notas.\n"
    "- Formato: Utiliza viñetas (bullet points) para una lectura clara y profesional."
)

DEFAULT_EN_INSTRUCTION = (
    "You are an expert secondhand goods reseller. Analyze the provided photos and field notes "
    "to draft a marketplace listing (for platforms like eBay, Vinted, Wallapop).\n\n"
    "INSTRUCTIONS:\n"
    "- Language: Draft the title and description COMPLETELY IN ENGLISH.\n"
    "- Title: Clear, concise, keyword-rich (Brand, model, key style, condition).\n"
    "- Description: Engaging sales pitch, item details, condition assessment, and explicit mention of any flaws.\n"
    "- Format: Use bullet points where appropriate for clean readability."
)


class AIServiceError(Exception):
    """Custom exception raised when AI generation fails."""
    pass


class ProductListingSchema(BaseModel):
    title: str = Field(description="Catchy, SEO-optimized title with brand, model, color, and size")
    description: str = Field(description="Structured sales description highlighting features, condition, and flaws")
    category_slug: Optional[OfficialCategorySlug] = Field(
        default=None,
        description="Official Rápido Pack category slug that best matches the product",
    )
    condition: Optional[OfficialConditionCode] = Field(
        default=None,
        description="Official physical condition state: new_with_tags, very_good, good, or vintage",
    )


class IntakePreflightSchema(BaseModel):
    identified_title: str = Field(description="Detected product brand, model, and item type")
    category: str = Field(description="High-level product category")
    category_slug: Optional[OfficialCategorySlug] = Field(
        default=None,
        description="Official Rápido Pack category slug that best matches the product",
    )
    condition: Optional[OfficialConditionCode] = Field(
        default=None,
        description="Official physical condition state: new_with_tags, very_good, good, or vintage",
    )
    detected_attributes: list[str] = Field(default_factory=list, description="Visible attributes such as color, materials, logos")
    missing_or_recommended_info: list[str] = Field(default_factory=list, description="Actionable checklist of missing tags, size labels, flaws, or angles")
    suggested_note: str = Field(description="Draft summary suitable for intake notes")
    estimated_retail_price: Optional[float] = Field(
        default=None,
        description="Estimated original retail price when brand new in Euros (€) (MSRP). Null if impossible to estimate."
    )
    estimated_resale_price: Optional[float] = Field(
        default=None,
        description="Estimated realistic secondhand market resale value in Euros (€) considering condition in Spain/Europe. Null if impossible to estimate."
    )


_CATEGORY_KEYWORD_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("moda-y-accesorios", ("camiseta", "chaqueta", "biker", "gabardina", "pantalon", "pantalón", "vaquero", "levi", "nike", "adidas", "zara", "burberry", "vestido", "abrigo", "bolso", "zapatilla", "zapato", "bota", "sudadera", "reloj", "seiko", "gafas", "cinturon", "cinturón", "shirt", "jacket", "jeans", "sneakers", "dress", "hoodie", "tee")),
    ("bicicletas", ("bici", "bicicleta", "orbea", "shimano", "trek", "bh ", "mtb", "ciclismo", "casco de bicicleta", "bicycle", "brompton")),
    ("electrodomesticos", ("lavadora", "nevera", "frigorifico", "frigorífico", "microondas", "aspiradora", "robot", "cafetera", "horno", "tostadora", "sandwichera", "freidora", "plancha", "ventilador", "calefactor", "termoventilador", "olla", "moldeador", "cortapelos", "irrigador", "batidora", "dyson", "cecotec", "rowenta", "philips", "braun", "tristar")),
    ("tecnologia-y-electronica", ("iphone", "samsung", "sony", "consola", "ps5", "ps4", "nintendo", "switch", "gamepad", "mando", "portatil", "portátil", "macbook", "ipad", "camara", "cámara", "olympus", "leica", "canon", "nikon", "objetivo", "prismaticos", "prismáticos", "auriculares", "altavoz", "marshall", "teclado", "keychron", "walkman", "televisor", "monitor", "telefono", "teléfono", "gigaset", "hikvision", "estacion", "estación", "bateria", "batería", "laptop", "tablet", "phone", "camera")),
    ("cine-libros-y-musica", ("libro", "novela", "vinilo", "tocadiscos", "audio-technica", "disco", "guitarra", "yamaha", "amplificador", "dvd", "bluray", "blu-ray", "cd ", "pelicula", "película", "teclado musical", "book", "vinyl")),
    ("deporte-y-ocio", ("raqueta", "padel", "pádel", "tenis", "pesa", "mancuerna", "patinete", "monopatin", "monopatín", "surfskate", "carver", "mochila", "osprey", "camping", "tienda de campaña", "esqui", "esquí", "surf", "balon", "balón", "deporte", "gym", "fitness")),
    ("motor-y-accesorios", ("moto", "casco de moto", "coche", "neumatico", "neumático", "llanta", "carburador", "escape", "scooter")),
    ("ninos-y-bebes", ("bebe", "bebé", "carrito", "cuna", "juguete", "lego", "playmobil", "infantil", "trona", "baby", "stroller")),
    ("coleccionismo", ("coleccion", "colección", "antiguo", "antigüedad", "moneda", "sello", "figura", "funko", "murano", "pluma estilografica", "pluma estilográfica", "pelikan", "coleccionismo", "collectible")),
    ("construccion-y-reformas", ("taladro", "sierra", "radial", "bosch", "makita", "dewalt", "herramienta", "escalera", "compresor", "soldador", "reforma", "bricolaje")),
    ("industria-y-agricultura", ("industrial", "agricola", "agrícola", "generador", "motobomba", "desbrozadora", "motosierra", "maquinaria", "transpaleta")),
    ("hogar-y-jardin", ("mesa", "silla", "herman miller", "sofa", "sofá", "armario", "lampara", "lámpara", "espejo", "estanteria", "estantería", "alfombra", "jardin", "jardín", "mueble", "ceramica", "cerámica", "decoracion", "decoración")),
)


def infer_taxonomy_heuristically(text: str) -> Tuple[str, str]:
    """
    Deterministic keyword heuristic fallback for classifying a product into one of the
    12 official Rápido Pack category slugs and 4 official condition states.
    """
    lowered = (text or "").lower()

    category_slug = "moda-y-accesorios"
    for slug, keywords in _CATEGORY_KEYWORD_MAP:
        if any(kw in lowered for kw in keywords):
            category_slug = slug
            break
    else:
        category_slug = "hogar-y-jardin"

    if any(kw in lowered for kw in ("nuevo con etiqueta", "new with tag", "precintado", "a estrenar", "brand new", "nwt", "sin abrir")):
        condition = ProductCondition.NEW_WITH_TAGS
    elif any(kw in lowered for kw in ("vintage", "años 80", "años 90", "80s", "90s", "199", "198", "retro", "clásico", "clasico")):
        condition = ProductCondition.VINTAGE
    elif any(kw in lowered for kw in ("perfecto estado", "como nuevo", "muy buen estado", "impecable", "excelente", "very good", "like new", "great condition")):
        condition = ProductCondition.VERY_GOOD
    else:
        condition = ProductCondition.GOOD

    return category_slug, condition


PREFLIGHT_ES_INSTRUCTION = (
    "Eres un asistente de tasación e inventario para una tienda de artículos de segunda mano y vintage.\n"
    "Analiza rápidamente las fotos del producto (hasta 3 fotos) y las notas preliminares para identificar el artículo, "
    "estimar su tasación de mercado y señalar qué detalles cruciales faltan para una catalogación completa.\n\n"
    "INSTRUCCIONES:\n"
    "- Idioma: Responde COMPLETAMENTE EN ESPAÑOL.\n"
    "- identified_title: Marca, modelo o tipo de prenda/objeto reconocido.\n"
    "- category: Categoría general (ej. Calzado, Ropa Vintage, Electrónica, Accesorios).\n"
    "- detected_attributes: Lista de atributos visibles (color, materiales, estampados, cortes).\n"
    "- missing_or_recommended_info: Lista breve de datos o fotos que faltan o se recomienda revisar "
    "(ej. 'Falta foto de la etiqueta de talla/composición', 'Revisar desgaste en suela o cremalleras', 'Indicar medidas').\n"
    "- suggested_note: Resumen breve y útil que el asistente puede añadir a sus notas de campo.\n"
    "- estimated_retail_price: Estimación numérica en Euros (€) del precio original de venta nuevo en tienda (PVP nuevo / MSRP). Devuelve null si es artesanal, sin marca o imposible de tasar objetivamente.\n"
    "- estimated_resale_price: Estimación numérica en Euros (€) del valor de reventa realista en el mercado de segunda mano en España/Europa (Wallapop, Vinted, eBay) según el estado detectado. Devuelve null si no es tasable objetivamente."
)

PREFLIGHT_EN_INSTRUCTION = (
    "You are an intake and appraisal assistant for a secondhand and vintage goods shop.\n"
    "Quickly inspect the product photos (up to 3 photos) and preliminary notes to identify the item, "
    "estimate its market valuation, and flag any crucial inspection details missing for full cataloging.\n\n"
    "INSTRUCTIONS:\n"
    "- Language: Respond COMPLETELY IN ENGLISH.\n"
    "- identified_title: Recognized brand, model, or item type.\n"
    "- category: High-level category (e.g., Footwear, Vintage Clothing, Electronics, Accessories).\n"
    "- detected_attributes: List of visible attributes (colorway, materials, logos, cuts).\n"
    "- missing_or_recommended_info: Short list of missing details or recommended inspection steps "
    "(e.g., 'Size or care tag not clearly visible', 'Inspect underside sole wear', 'Check zippers or seams').\n"
    "- suggested_note: Concise summary that the assistant can add to field notes.\n"
    "- estimated_retail_price: Numeric estimate in Euros (€) of the original retail price when brand new in store (MSRP). Return null if unbranded, handmade, or impossible to estimate objectively.\n"
    "- estimated_resale_price: Numeric estimate in Euros (€) of the realistic secondhand market resale value in Spain/Europe (Wallapop, Vinted, eBay) considering detected condition. Return null if impossible to estimate objectively."
)


def resolve_ai_configuration(language: str = "en") -> Tuple[str, float, str]:
    """
    Retrieves the active AIPromptConfiguration for the specified language.
    Falls back gracefully to hardcoded constants if no record is found or on database errors.
    Returns: (model_name, temperature, system_instruction)
    """
    lang_code = "es" if str(language).lower().startswith("es") else "en"
    try:
        from inventory.models import AIPromptConfiguration
        config = AIPromptConfiguration.objects.filter(
            language=lang_code,
            is_active=True
        ).first()
        if config and config.system_instruction and config.system_instruction.strip():
            model = (config.model_name or "").strip() or DEFAULT_MODEL_NAME
            temp = config.temperature if config.temperature is not None else DEFAULT_TEMPERATURE
            return model, temp, config.system_instruction.strip()
    except Exception as exc:
        logger.warning("Could not retrieve AIPromptConfiguration from database: %s. Using default fallback.", exc)

    default_instruction = DEFAULT_ES_INSTRUCTION if lang_code == "es" else DEFAULT_EN_INSTRUCTION
    return DEFAULT_MODEL_NAME, DEFAULT_TEMPERATURE, default_instruction


def generate_product_listing(
    product: Product,
    model_name: Optional[str] = None,
    language: str = "en",
) -> Dict[str, str]:
    """
    Sends product photos and preserved raw notes to Gemini Multimodal Vision API.
    Uses dynamic model, temperature, and instructions from AIPromptConfiguration with fallback.
    Returns a dictionary with 'title' and 'description' matched to the target language.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key.strip():
        raise AIServiceError("GEMINI_API_KEY is not configured in environment or settings.")

    images = list(product.images.all()[:5])
    if not images and not (product.raw_note and product.raw_note.strip()):
        raise AIServiceError("Cannot generate listing: Product has no photos and no field notes.")

    # 1. Resolve configuration & copywriting instructions
    resolved_model, resolved_temp, system_instruction = resolve_ai_configuration(language)
    active_model = model_name.strip() if (model_name and model_name.strip()) else resolved_model

    is_es = str(language).lower().startswith("es")
    notes_header = "NOTAS DE CAMPO DE LA ENTRADA:" if is_es else "FIELD NOTES FROM INTAKE:"
    notes_fallback = "No se proporcionaron notas." if is_es else "None provided."
    notes_text = product.raw_note.strip() if (product.raw_note and product.raw_note.strip()) else notes_fallback

    # Format resolved clarifications if any
    resolved_clarifications = product.clarifications.filter(status=ClarificationStatus.RESOLVED).order_by("created_at")
    clarifications_text = ""
    if resolved_clarifications.exists():
        if is_es:
            clarifications_header = "\n\nACLARACIONES Y RESPUESTAS DEL ASISTENTE:"
        else:
            clarifications_header = "\n\nCLARIFICATIONS AND ASSISTANT ANSWERS:"

        clarif_lines = []
        for c in resolved_clarifications:
            cat_display = c.get_category_display()
            if is_es:
                clarif_lines.append(f"- [{cat_display}] Pregunta: {c.question} -> Respuesta: {c.answer}")
            else:
                clarif_lines.append(f"- [{cat_display}] Question: {c.question} -> Answer: {c.answer}")

        clarifications_text = clarifications_header + "\n" + "\n".join(clarif_lines)

    prompt_text = (
        f"{system_instruction}\n\n"
        f"{notes_header}\n"
        f"{notes_text}"
        f"{clarifications_text}"
    )

    contents = [prompt_text]

    # 2. Attach image bytes
    for idx, img_obj in enumerate(images):
        try:
            with img_obj.image.open("rb") as f:
                img_bytes = f.read()
                contents.append(
                    types.Part.from_bytes(data=img_bytes, mime_type="image/webp")
                )
        except Exception as e:
            logger.warning(f"Could not read image {img_obj.id} for AI analysis: {e}")

    # 3. Call Gemini
    try:
        client = genai.Client(api_key=api_key.strip())
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ProductListingSchema,
            temperature=resolved_temp,
        )
        response = client.models.generate_content(
            model=active_model,
            contents=contents,
            config=config,
        )

        if hasattr(response, "parsed") and response.parsed:
            parsed = response.parsed
            raw_cat = (getattr(parsed, "category_slug", None) or "").strip()
            raw_cond = (getattr(parsed, "condition", None) or "").strip()
            return {
                "title": getattr(parsed, "title", "").strip(),
                "description": getattr(parsed, "description", "").strip(),
                "category_slug": raw_cat if raw_cat in VALID_CATEGORY_SLUGS else "",
                "condition": raw_cond if raw_cond in VALID_CONDITION_CODES else "",
            }

        # Fallback to json text parsing
        data = json.loads(response.text)
        raw_cat = str(data.get("category_slug") or "").strip()
        raw_cond = str(data.get("condition") or "").strip()
        return {
            "title": data.get("title", "").strip(),
            "description": data.get("description", "").strip(),
            "category_slug": raw_cat if raw_cat in VALID_CATEGORY_SLUGS else "",
            "condition": raw_cond if raw_cond in VALID_CONDITION_CODES else "",
        }

    except Exception as exc:
        logger.error(f"Gemini API request failed: {exc}", exc_info=True)
        raise AIServiceError(f"AI generation failed: {exc}") from exc


def _detect_mime_type(data: bytes) -> str:
    """Helper to detect image MIME type from initial bytes."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "image/webp"
    return "image/jpeg"


def _clean_price(val: object) -> Optional[float]:
    """Helper to validate, sanitize, and round float pricing estimates."""
    if val is None:
        return None
    try:
        f = float(val)
        if f < 0 or f > 9999999.99:
            return None
        return round(f, 2)
    except (ValueError, TypeError):
        return None


def identify_intake_product(
    images_bytes: list[bytes],
    raw_note: str = "",
    language: str = "es",
) -> dict:
    """
    Analyzes uploaded product images during intake using Gemini Multimodal Vision API.
    Caps image inputs to the first 3 photos for rapid mobile response and lower token usage.
    Returns structured JSON with identified_title, category, detected_attributes,
    missing_or_recommended_info, and suggested_note.
    Does not raise unhandled exceptions; returns { 'success': False, 'error': ... } on failure.
    """
    valid_images = [b for b in (images_bytes or []) if b][:3]
    note_clean = (raw_note or "").strip()

    is_es = str(language).lower().startswith("es")
    if not valid_images and not note_clean:
        return {
            "success": False,
            "error": "No se han proporcionado fotos ni notas para la identificación." if is_es else "No photos or notes provided for identification.",
        }

    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key.strip():
        return {
            "success": False,
            "error": "GEMINI_API_KEY is not configured in environment or settings.",
        }

    system_instruction = PREFLIGHT_ES_INSTRUCTION if is_es else PREFLIGHT_EN_INSTRUCTION
    notes_header = "NOTAS PRELIMINARES DEL ASISTENTE:" if is_es else "ASSISTANT PRELIMINARY NOTES:"
    notes_body = note_clean if note_clean else ("Ninguna nota proporcionada." if is_es else "None provided.")

    prompt_text = (
        f"{system_instruction}\n\n"
        f"{notes_header}\n"
        f"{notes_body}"
    )

    contents = [prompt_text]
    for img_data in valid_images:
        mime = _detect_mime_type(img_data)
        contents.append(types.Part.from_bytes(data=img_data, mime_type=mime))

    try:
        client = genai.Client(api_key=api_key.strip())
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=IntakePreflightSchema,
            temperature=0.2,
        )
        response = client.models.generate_content(
            model=INTAKE_IDENTIFICATION_MODEL_NAME,
            contents=contents,
            config=config,
        )

        if hasattr(response, "parsed") and response.parsed:
            parsed = response.parsed
            raw_cat = (getattr(parsed, "category_slug", None) or "").strip()
            raw_cond = (getattr(parsed, "condition", None) or "").strip()
            return {
                "success": True,
                "identified_title": getattr(parsed, "identified_title", "").strip(),
                "category": getattr(parsed, "category", "").strip(),
                "category_slug": raw_cat if raw_cat in VALID_CATEGORY_SLUGS else "",
                "condition": raw_cond if raw_cond in VALID_CONDITION_CODES else "",
                "detected_attributes": list(getattr(parsed, "detected_attributes", []) or []),
                "missing_or_recommended_info": list(getattr(parsed, "missing_or_recommended_info", []) or []),
                "suggested_note": getattr(parsed, "suggested_note", "").strip(),
                "estimated_retail_price": _clean_price(getattr(parsed, "estimated_retail_price", None)),
                "estimated_resale_price": _clean_price(getattr(parsed, "estimated_resale_price", None)),
            }

        # Fallback to json text parsing
        data = json.loads(response.text)
        raw_cat = str(data.get("category_slug") or "").strip()
        raw_cond = str(data.get("condition") or "").strip()
        return {
            "success": True,
            "identified_title": str(data.get("identified_title", "")).strip(),
            "category": str(data.get("category", "")).strip(),
            "category_slug": raw_cat if raw_cat in VALID_CATEGORY_SLUGS else "",
            "condition": raw_cond if raw_cond in VALID_CONDITION_CODES else "",
            "detected_attributes": list(data.get("detected_attributes", []) or []),
            "missing_or_recommended_info": list(data.get("missing_or_recommended_info", []) or []),
            "suggested_note": str(data.get("suggested_note", "")).strip(),
            "estimated_retail_price": _clean_price(data.get("estimated_retail_price")),
            "estimated_resale_price": _clean_price(data.get("estimated_resale_price")),
        }
    except Exception as exc:
        logger.error(f"Gemini preflight identification failed: {exc}", exc_info=True)
        return {
            "success": False,
            "error": f"Error en la identificación con IA: {exc}" if is_es else f"AI identification failed: {exc}",
        }
