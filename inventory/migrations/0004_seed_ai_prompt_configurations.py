from django.db import migrations


def seed_default_ai_configurations(apps, schema_editor):
    AIPromptConfiguration = apps.get_model('inventory', 'AIPromptConfiguration')

    es_instruction = (
        "Eres un experto en reventa y comercialización de artículos de segunda mano y vintage. "
        "Analiza las fotos adjuntas y las notas de campo para redactar una publicación de marketplace (para Wallapop, Vinted, eBay).\n\n"
        "INSTRUCCIONES:\n"
        "- Idioma: Redacta el título y la descripción COMPLETAMENTE EN ESPAÑOL.\n"
        "- Título: Claro, conciso y rico en palabras clave (Marca, modelo, estilo principal, estado).\n"
        "- Descripción: Argumento de venta atractivo, detalles del artículo, evaluación del estado y mención explícita de cualquier defecto o desgaste observado en las fotos o notas.\n"
        "- Formato: Utiliza viñetas (bullet points) para una lectura clara y profesional."
    )

    en_instruction = (
        "You are an expert secondhand goods reseller. Analyze the provided photos and field notes "
        "to draft a marketplace listing (for platforms like eBay, Vinted, Wallapop).\n\n"
        "INSTRUCTIONS:\n"
        "- Language: Draft the title and description COMPLETELY IN ENGLISH.\n"
        "- Title: Clear, concise, keyword-rich (Brand, model, key style, condition).\n"
        "- Description: Engaging sales pitch, item details, condition assessment, and explicit mention of any flaws.\n"
        "- Format: Use bullet points where appropriate for clean readability."
    )

    AIPromptConfiguration.objects.create(
        language="es",
        model_name="gemini-2.5-flash",
        temperature=0.3,
        system_instruction=es_instruction,
        is_active=True,
    )

    AIPromptConfiguration.objects.create(
        language="en",
        model_name="gemini-2.5-flash",
        temperature=0.3,
        system_instruction=en_instruction,
        is_active=True,
    )


def unseed_default_ai_configurations(apps, schema_editor):
    AIPromptConfiguration = apps.get_model('inventory', 'AIPromptConfiguration')
    AIPromptConfiguration.objects.filter(language__in=["es", "en"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_aipromptconfiguration'),
    ]

    operations = [
        migrations.RunPython(seed_default_ai_configurations, unseed_default_ai_configurations),
    ]
