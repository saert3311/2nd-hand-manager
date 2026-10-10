import json
import logging
from typing import Dict

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from inventory.models import Product

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Custom exception raised when AI generation fails."""
    pass


class ProductListingSchema(BaseModel):
    title: str = Field(description="Catchy, SEO-optimized title with brand, model, color, and size")
    description: str = Field(description="Structured sales description highlighting features, condition, and flaws")


def generate_product_listing(
    product: Product,
    model_name: str = "gemini-2.5-flash",
    language: str = "en",
) -> Dict[str, str]:
    """
    Sends product photos and preserved raw notes to Gemini Multimodal Vision API.
    Returns a dictionary with 'title' and 'description' matched to the target language.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    if not api_key.strip():
        raise AIServiceError("GEMINI_API_KEY is not configured in environment or settings.")

    images = list(product.images.all()[:5])
    if not images and not product.raw_note.strip():
        raise AIServiceError("Cannot generate listing: Product has no photos and no field notes.")

    contents = []

    # 1. System & contextual instructions matched to language
    if str(language).lower().startswith("es"):
        prompt_text = (
            "Eres un experto en reventa y comercialización de artículos de segunda mano y vintage. "
            "Analiza las fotos adjuntas y las notas de campo para redactar una publicación de marketplace (para Wallapop, Vinted, eBay).\n\n"
            f"NOTAS DE CAMPO DE LA ENTRADA:\n{product.raw_note.strip() if product.raw_note else 'No se proporcionaron notas.'}\n\n"
            "INSTRUCCIONES:\n"
            "- Idioma: Redacta el título y la descripción COMPLETAMENTE EN ESPAÑOL.\n"
            "- Título: Claro, conciso y rico en palabras clave (Marca, modelo, estilo principal, estado).\n"
            "- Descripción: Argumento de venta atractivo, detalles del artículo, evaluación del estado y mención explícita de cualquier defecto o desgaste observado en las fotos o notas.\n"
            "- Formato: Utiliza viñetas (bullet points) para una lectura clara y profesional."
        )
    else:
        prompt_text = (
            "You are an expert secondhand goods reseller. Analyze the provided photos and field notes "
            "to draft a marketplace listing (for platforms like eBay, Vinted, Wallapop).\n\n"
            f"FIELD NOTES FROM INTAKE:\n{product.raw_note.strip() if product.raw_note else 'None provided.'}\n\n"
            "INSTRUCTIONS:\n"
            "- Language: Draft the title and description COMPLETELY IN ENGLISH.\n"
            "- Title: Clear, concise, keyword-rich (Brand, model, key style, condition).\n"
            "- Description: Engaging sales pitch, item details, condition assessment, and explicit mention of any flaws.\n"
            "- Format: Use bullet points where appropriate for clean readability."
        )

    contents.append(prompt_text)

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
            temperature=0.3,
        )
        response = client.models.generate_content(
            model=model_name,
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
