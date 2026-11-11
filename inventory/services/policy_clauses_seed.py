from typing import Any

from inventory.models import PolicySeverity

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
