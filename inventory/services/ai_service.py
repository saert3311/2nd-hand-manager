import json
import logging
from typing import Dict, Optional, Tuple

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from inventory.models import ClarificationStatus, Product

logger = logging.getLogger(__name__)

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


class IntakePreflightSchema(BaseModel):
    identified_title: str = Field(description="Detected product brand, model, and item type")
    category: str = Field(description="High-level product category")
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
            return {
                "title": getattr(parsed, "title", "").strip(),
                "description": getattr(parsed, "description", "").strip(),
            }

        # Fallback to json text parsing
        data = json.loads(response.text)
        return {
            "title": data.get("title", "").strip(),
            "description": data.get("description", "").strip(),
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
            return {
                "success": True,
                "identified_title": getattr(parsed, "identified_title", "").strip(),
                "category": getattr(parsed, "category", "").strip(),
                "detected_attributes": list(getattr(parsed, "detected_attributes", []) or []),
                "missing_or_recommended_info": list(getattr(parsed, "missing_or_recommended_info", []) or []),
                "suggested_note": getattr(parsed, "suggested_note", "").strip(),
                "estimated_retail_price": _clean_price(getattr(parsed, "estimated_retail_price", None)),
                "estimated_resale_price": _clean_price(getattr(parsed, "estimated_resale_price", None)),
            }

        # Fallback to json text parsing
        data = json.loads(response.text)
        return {
            "success": True,
            "identified_title": str(data.get("identified_title", "")).strip(),
            "category": str(data.get("category", "")).strip(),
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
