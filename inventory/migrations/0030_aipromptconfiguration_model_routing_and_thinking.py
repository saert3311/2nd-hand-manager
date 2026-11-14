from django.db import migrations, models


def upgrade_legacy_default_model(apps, schema_editor):
    AIPromptConfiguration = apps.get_model("inventory", "AIPromptConfiguration")
    AIPromptConfiguration.objects.filter(model_name="gemini-2.5-flash").update(
        model_name="gemini-4-hydrogen",
        thinking_level="low",
    )


def revert_legacy_default_model(apps, schema_editor):
    AIPromptConfiguration = apps.get_model("inventory", "AIPromptConfiguration")
    AIPromptConfiguration.objects.filter(model_name="gemini-4-hydrogen").update(
        model_name="gemini-2.5-flash",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0029_seed_default_walkin_provider"),
    ]

    operations = [
        migrations.AddField(
            model_name="aipromptconfiguration",
            name="compliance_model_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional model override for ClauseGuard Stage 2 verification. Leave blank to inherit Model Name.",
                max_length=64,
                verbose_name="Compliance Check Model Override",
            ),
        ),
        migrations.AddField(
            model_name="aipromptconfiguration",
            name="intake_model_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional model override for intake pre-flight identification. Leave blank to inherit Model Name.",
                max_length=64,
                verbose_name="Intake Vision Model Override",
            ),
        ),
        migrations.AddField(
            model_name="aipromptconfiguration",
            name="policy_sync_model_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional model override for marketplace Terms & Conditions extraction. Leave blank to inherit Model Name.",
                max_length=64,
                verbose_name="Policy Sync Model Override",
            ),
        ),
        migrations.AddField(
            model_name="aipromptconfiguration",
            name="thinking_level",
            field=models.CharField(
                choices=[
                    ("minimal", "Minimal (Near-Off — Auto-clamps to Low on Gemini 4 & 3.8)"),
                    ("low", "Low Effort — Fast & Cost-Efficient (Recommended)"),
                    ("medium", "Medium Effort — Balanced Reasoning"),
                    ("high", "High Effort — Deep Reasoning (Higher Token Cost)"),
                ],
                default="low",
                help_text="Controls internal reasoning token spend and latency. 'Low' is recommended to avoid overthinking and excess output token charges on Gemini 4 and 3.8 models.",
                max_length=16,
                verbose_name="Thinking Effort Level",
            ),
        ),
        migrations.AlterField(
            model_name="aipromptconfiguration",
            name="model_name",
            field=models.CharField(
                default="gemini-4-hydrogen",
                help_text="Primary Gemini model identifier (used for listing copywriting and as default for all other AI tasks).",
                max_length=64,
                verbose_name="Model Name",
            ),
        ),
        migrations.RunPython(upgrade_legacy_default_model, revert_legacy_default_model),
    ]
