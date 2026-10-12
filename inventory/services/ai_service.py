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
