import io
import os
import sys
from decimal import Decimal
from datetime import datetime, timezone as dt_timezone
import django
from PIL import Image

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from inventory.models import Product, ProductImage
from inventory.services.storage import OCIObjectStorage

User = get_user_model()

SAMPLE_DATA = [
    {
        "ai_title": "Sony WH-1000XM4 Auriculares con cancelación de ruido",
        "raw_note": "Auriculares inalámbricos Sony negros, almohadillas en buen estado, incluye estuche y cable.",
        "sale_price": Decimal("180.00"),
        "is_sold": False,
        "date_offset_days": 1,
        "color": (30, 30, 30),
    },
    {
        "ai_title": "Chaqueta de cuero vintage negra talla L",
        "raw_note": "Cazadora motera auténtica de piel vacuno, cremalleras metálicas YKK, ligero desgaste en puños.",
        "sale_price": Decimal("120.00"),
        "is_sold": True,
        "sold_price": Decimal("110.00"),
        "date_offset_days": 2,
        "color": (60, 40, 20),
    },
    {
        "ai_title": "Mesa de centro rústica de roble macizo",
        "raw_note": "Mesa baja hecha a mano en madera de roble, acabado al aceite natural, 100x60 cm.",
        "sale_price": Decimal("95.00"),
        "is_sold": False,
        "date_offset_days": 3,
        "color": (150, 110, 60),
    },
    {
        "ai_title": "Teclado mecánico Keychron K2 RGB interruptores marrones",
        "raw_note": "Teclado 75% inalámbrico Bluetooth/USB-C, switches Gateron Brown táctiles, layout ISO español.",
        "sale_price": Decimal("75.00"),
        "is_sold": False,
        "date_offset_days": 4,
        "color": (40, 70, 120),
    },
    {
        "ai_title": "Casco de bicicleta Bell Stratus MIPS talla M",
        "raw_note": "Casco de carretera ventilado, sistema MIPS protección contra impactos, color blanco mate.",
        "sale_price": Decimal("50.00"),
        "is_sold": True,
        "sold_price": Decimal("45.00"),
        "date_offset_days": 5,
        "color": (200, 200, 200),
    },
    {
        "ai_title": "Reloj Seiko 5 automático esfera azul 37mm",
        "raw_note": "Reloj mecánico calibre 7S26, correa de acero inoxidable, funcionando con precisión.",
        "sale_price": Decimal("110.00"),
        "is_sold": False,
        "date_offset_days": 6,
        "color": (20, 50, 140),
    },
    {
        "ai_title": "Lámpara de pie de latón estilo Art Déco",
        "raw_note": "Lámpara vintage dorada con pantalla de cristal opalino, casquillo E27, cableado renovado.",
        "sale_price": Decimal("85.00"),
        "is_sold": False,
        "date_offset_days": 7,
        "color": (180, 150, 50),
    },
    {
        "ai_title": "Mochila Osprey Farpoint 40L para viaje",
        "raw_note": "Mochila de cabina tamaño avión, arnés guardable, compartimento acolchado para portátil.",
        "sale_price": Decimal("90.00"),
        "is_sold": True,
        "sold_price": Decimal("85.00"),
        "date_offset_days": 8,
        "color": (40, 100, 70),
    },
    {
        "ai_title": "Tocadiscos Audio-Technica AT-LP120XUSB",
        "raw_note": "Giradiscos tracción directa con previo de fono integrado, salida USB para digitalizar vinilos.",
        "sale_price": Decimal("240.00"),
        "is_sold": False,
        "date_offset_days": 9,
        "color": (70, 70, 70),
    },
    {
        "ai_title": "Guitarra clásica Yamaha C40 con funda acolchada",
        "raw_note": "Guitarra acústica de iniciación cuerdas de nylon, tapa de abeto, sonido cálido y afinación estable.",
        "sale_price": Decimal("65.00"),
        "is_sold": False,
        "date_offset_days": 10,
        "color": (190, 130, 70),
    },
    {
        "ai_title": "Cafetera espresso De'Longhi Dedica roja bomba 15 bar",
        "raw_note": "Cafetera de brazo compacta acero inoxidable, vaporizador de leche para cappuccino, descalcificada.",
        "sale_price": Decimal("99.00"),
        "is_sold": True,
        "sold_price": Decimal("90.00"),
        "date_offset_days": 12,
        "color": (180, 30, 30),
    },
    {
        "ai_title": "Silla ergonómica Herman Miller Sayl blanca y gris",
        "raw_note": "Silla de oficina respaldo 3D suspension inteligente, soporte lumbar ajustable, ruedas silenciosas.",
        "sale_price": Decimal("350.00"),
        "is_sold": False,
        "date_offset_days": 15,
        "color": (220, 220, 220),
    },
    {
        "ai_title": "Juego de té japonés de cerámica artesanal Kyusu",
        "raw_note": "Tetera con asa lateral y 4 cuencos de gres con esmalte azul marino, sin grietas.",
        "sale_price": Decimal("40.00"),
        "is_sold": False,
        "date_offset_days": 18,
        "color": (30, 60, 90),
    },
    {
        "ai_title": "Prismáticos Nikon Monarch 8x42 impermeables",
        "raw_note": "Binoculares para observación de aves con prismas roof ED y revestimiento multicapa.",
        "sale_price": Decimal("195.00"),
        "is_sold": False,
        "date_offset_days": 20,
        "color": (40, 50, 40),
    },
    {
        "ai_title": "Consola Nintendo Switch OLED blanca completa",
        "raw_note": "Consola híbrida pantalla OLED 7 pulgadas con dock, Joy-Con blancos, cargador original y funda.",
        "sale_price": Decimal("260.00"),
        "is_sold": True,
        "sold_price": Decimal("250.00"),
        "date_offset_days": 22,
        "color": (240, 240, 240),
    },
    {
        "ai_title": "Pluma estilográfica Pelikan Souverän M400 verde estriado",
        "raw_note": "Pluma clásica con plumín de oro bicolor 14K trazo F, sistema de émbolo diferencial.",
        "sale_price": Decimal("220.00"),
        "is_sold": False,
        "date_offset_days": 25,
        "color": (30, 90, 50),
    },
    {
        "ai_title": "Monopatín Carver Surfskate CX 31 pulgadas",
        "raw_note": "Tabla para entrenamiento de surf urbano, ejes Carver CX, ruedas cóncavas Roundhouse 69mm.",
        "sale_price": Decimal("140.00"),
        "is_sold": False,
        "date_offset_days": 28,
        "color": (160, 100, 40),
    },
    {
        "ai_title": "Altavoz Bluetooth Marshall Emberton II negro y latón",
        "raw_note": "Altavoz portátil resistente al agua IP67, sonido multidireccional True Stereophonic, 30h batería.",
        "sale_price": Decimal("115.00"),
        "is_sold": False,
        "date_offset_days": 32,
        "color": (20, 20, 20),
    },
    {
        "ai_title": "Chaqueta impermeable Patagonia Torrentshell 3L azul",
        "raw_note": "Chubasquero técnico montaña membrana H2No Performance Standard, cremalleras axilares.",
        "sale_price": Decimal("95.00"),
        "is_sold": True,
        "sold_price": Decimal("85.00"),
        "date_offset_days": 35,
        "color": (20, 80, 160),
    },
    {
        "ai_title": "Objetivo Canon EF 50mm f/1.4 USM montura EF",
        "raw_note": "Lente luminosa para retrato fotográfico, motor ultrasónico de enfoque rápido, lentes limpias.",
        "sale_price": Decimal("160.00"),
        "is_sold": False,
        "date_offset_days": 40,
        "color": (50, 50, 50),
    },
    {
        "ai_title": "Zapatillas vintage Nike Blazer Mid 77 talla 42",
        "raw_note": "Sneakers caña alta piel blanca con swoosh negro, puntera de ante gris, suela de espiga vintage.",
        "sale_price": Decimal("55.00"),
        "is_sold": False,
        "date_offset_days": 45,
        "color": (230, 230, 230),
    },
    {
        "ai_title": "Jarrón de cristal de Murano soplado a mano azul cobalto",
        "raw_note": "Pieza de coleccionismo italiano vintage años 70, base pulida, sin muescas ni golpes.",
        "sale_price": Decimal("70.00"),
        "is_sold": False,
        "date_offset_days": 50,
        "color": (10, 40, 180),
    },
]


def create_sample_webp(color=(100, 100, 100)):
    img = Image.new("RGB", (120, 120), color=color)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=80)
    return buf.getvalue()


def seed_database():
    assistant_user = User.objects.filter(username="assistant").first()
    manager_user = User.objects.filter(username="manager").first()
    if not assistant_user or not manager_user:
        print("Run 'python manage.py setup_roles' first!")
        return

    base_time = timezone.now()
    created_count = 0

    for i, data in enumerate(SAMPLE_DATA):
        # Check if already seeded
        if Product.objects.filter(ai_title=data["ai_title"]).exists():
            continue

        creator = assistant_user if (i % 3 != 0) else manager_user
        created_time = base_time - timezone.timedelta(days=data["date_offset_days"])

        product = Product(
            ai_title=data["ai_title"],
            raw_note=data["raw_note"],
            ai_description=f"<p>{data['raw_note']}</p><p>Garantía de calidad y envío rápido.</p>",
            sale_price=data["sale_price"],
            is_sold=data["is_sold"],
            created_by=creator,
        )
        if data["is_sold"]:
            product.sold_at = created_time + timezone.timedelta(hours=12)
            if "sold_price" in data:
                product.sale_price = data["sold_price"]

        product.save()

        # Update timestamps explicitly
        Product.objects.filter(pk=product.pk).update(
            created_at=created_time,
            updated_at=created_time,
        )

        # Attach sample image
        webp_bytes = create_sample_webp(data["color"])
        img_name = f"seed_product_{product.pk}.webp"
        pimg = ProductImage(product=product, order=0)
        pimg.image.save(img_name, ContentFile(webp_bytes), save=True)

        created_count += 1

    total_products = Product.objects.count()
    print(f"Successfully seeded {created_count} products. Total products now: {total_products}")


if __name__ == "__main__":
    seed_database()
