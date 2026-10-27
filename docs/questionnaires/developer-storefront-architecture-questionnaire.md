# Cuestionario de Arquitectura e Implementación para el Desarrollador (Storefront Fase 1 -> Fase 2)

> **Propósito de este documento:**  
> Estructurar todas las decisiones técnicas y de arquitectura antes de escribir el PRD e implementar el escaparate público (*Public Marketplace Storefront*) sobre [`2ndHand Staging Hub`](file:///C:/Users/Jose/antigravity/epic-tesla/README.md).
>
> Este cuestionario aplica las metodologías de `/interview-me` (cada decisión incluye una **Hipótesis / Arquitectura Recomendada** con sus razones) y `/idea-refine` (evaluación de alternativas, supuestos técnicos ocultos y compatibilidad hacia adelante con el **Carrito y Pasarela de Pago de la Fase 2**).

---

## Bloque 1: Estructura de Apps en Django y Enrutamiento URL (`urls.py`)

Actualmente, [`config/urls.py`](file:///C:/Users/Jose/antigravity/epic-tesla/config/urls.py) delega la raíz `''` a [`inventory/urls.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/urls.py), donde `path("", root_redirect_view, name="root")` exige autenticación (`@login_required`) y redirige a `/intake/` (Asistentes) o `/dashboard/` (Managers).

### D1.1. ¿Creamos una nueva app Django (`storefront`) o extendemos `inventory`?
- **Opciones:**
  - **Opción A (Recomendada — Nueva app `storefront/`):** Crear una aplicación Django dedicada `storefront` (vistas, URLs, plantillas públicas y tests aislados) que importe los modelos de `inventory.models`.
  - **Opción B (Todo en `inventory/`):** Añadir `public_catalog_view` y `public_product_detail_view` dentro de `inventory/views.py`.
- **Hipótesis / Recomendación (`GUESS`):** **Opción A (`storefront/`).** Separa limpiamente las vistas públicas sin `@login_required` de las vistas internas del staff, evita que un despiste de permisos en `inventory/views.py` exponga acciones de edición, y prepara el terreno para añadir `Cart`, `Order` y `Checkout` en la Fase 2 dentro de `storefront` (o `orders`) sin inflar `inventory`.
- **Decisión del Desarrollador:** `[x] Opción A Confirmada (App storefront/)   [ ] Opción B (Dentro de inventory/)`

### D1.2. Mapa de URLs públicas vs. URLs internas de gestión (actualizado: Landing + Tienda)

> **Cambio respecto a la versión anterior:** Rápido Pack no es solo una tienda: también es **punto de paquetería multimarca** (SEUR, GLS, InPost, Amazon, Kanguro, DHL) y **Punto Pack**. Por eso la raíz `/` pasa a ser la **landing corporativa del negocio** y el catálogo marketplace se mueve a **`/tienda/`**.

#### Mapa de URLs públicas (app `storefront`, sin `@login_required`)

| URL | Nombre (`name`) | Contenido |
| :--- | :--- | :--- |
| `/` | `storefront:home` | Landing corporativa: hero, agencias, servicios de paquetería, Punto Pack, identidad de marca ("Quiénes somos"), **4 productos más recientes**, ubicación y contacto. |
| `/#paqueteria`, `/#punto-pack`, `/#quienes-somos`, `/#contacto` | — (anclas) | Secciones de la landing enlazadas desde el menú principal. |
| `/tienda/` | `storefront:catalog` | Catálogo marketplace con buscador, filtros y ordenación por *query params*: `?q=`, `?estado=` (`nuevo-con-etiquetas`, `muy-bueno`, `buen-estado`, `vintage`), `?precio=` (`0-20`, `20-50`, `50-`), `?orden=` (`recientes`, `destacados`, `precio-asc`, `precio-desc`), `?page=`. |
| `/tienda/categoria/<slug:category_slug>/` | `storefront:category` | Catálogo filtrado por una de las 12 categorías, con URL indexable para SEO (ej. `/tienda/categoria/bicicletas/`). Acepta los mismos *query params*. |
| `/tienda/producto/<slug:slug>-<int:pk>/` | `storefront:product_detail` | Ficha pública del producto. Se busca por `pk`; si el `slug` no coincide con el título actual, se devuelve una **redirección 301 a la URL canónica**. |
| `/como-comprar/` | `storefront:how_to_buy` | Contenido del modal *"Saber más"* también disponible como página (reservas por WhatsApp, recogida gratis en Alfafar, envíos vía Wallapop/Vinted, pagos). Sirve como alternativa sin JavaScript y se puede compartir. |
| `/go/whatsapp/` | `storefront:go_whatsapp` | Redirección con conteo de clics al WhatsApp general de la tienda (CTA de la landing). |
| `/go/whatsapp/<int:pk>/` | `storefront:go_whatsapp_product` | Redirección con conteo de clics a `wa.me` con el mensaje del producto pre-rellenado. |
| `/go/link/<int:link_pk>/` | `storefront:go_listing` | Redirección con conteo de clics a un `ProductListingLink` activo (Wallapop/Vinted/eBay). |
| `/aviso-legal/`, `/privacidad/`, `/cookies/` | `storefront:legal_notice`, `storefront:privacy`, `storefront:cookies` | Páginas legales con plantillas estándar adaptadas a Rápido Pack. |
| `/sitemap.xml`, `/robots.txt` | — | Generados por Django (`django.contrib.sitemaps`). |

#### URLs internas (app `inventory`, sin cambios salvo la raíz)

| URL | Cambio |
| :--- | :--- |
| `/login/`, `/logout/`, `/dashboard/`, `/intake/`, `/intake/identify/`, `/products/<int:pk>/...` | **Sin cambios.** |
| `/admin/`, `/i18n/`, `/manifest.json`, `/sw.js`, `/api/push/...` | **Sin cambios.** |
| Antes `/` → ahora **`/panel/`** | `root_redirect_view` se mueve de `""` a `"panel/"` **conservando `name="root"`**. Así siguen funcionando `{% url 'inventory:root' %}` (logo de `inventory/base.html`) y los 3 tests de [`tests/test_auth.py`](file:///C:/Users/Jose/antigravity/epic-tesla/tests/test_auth.py) que usan `reverse("inventory:root")`. |

#### Notas de implementación
- **Orden en [`config/urls.py`](file:///C:/Users/Jose/antigravity/epic-tesla/config/urls.py):** incluir `storefront.urls` antes que `inventory.urls`, o eliminar la entrada `""` de `inventory/urls.py` (la que se mueve a `panel/`), para que no haya dos vistas compitiendo por `/`.
- **Login:** `LOGIN_REDIRECT_URL = 'inventory:dashboard'` y `LOGIN_URL = 'inventory:login'` en [`config/settings.py`](file:///C:/Users/Jose/antigravity/epic-tesla/config/settings.py) no cambian. El staff sigue entrando a `/login/` y llega al dashboard.
- **Barra de staff:** si el visitante está autenticado como `Assistant` o `Manager`, las páginas públicas muestran una barra fina con *"Ir al panel"* (`/panel/`) y *"Subir producto"* (`/intake/`).
- **Enlaces internos de la landing:** el botón *"Explorar la tienda"* y *"Ver toda la tienda →"* apuntan a `storefront:catalog`; las 4 tarjetas de *"Recién llegados"* apuntan a `storefront:product_detail`.
- **"Recién llegados" (landing):** `Product.objects.public_visible().filter(is_sold=False, is_reserved=False).order_by("-created_at")[:4]` con `prefetch_related` de la imagen principal.
- **Service worker:** `/sw.js` tiene scope `/` pero solo lo registra `inventory/base.html`, así que los visitantes públicos no lo instalan. Para el staff que ya lo tiene instalado, el modo *pass-through* no altera las páginas públicas.
- **Idiomas:** se mantiene `LocaleMiddleware` sin `i18n_patterns` (sin prefijo `/es/` ni `/en/`). El idioma de la interfaz se negocia con `Accept-Language` o con el selector `/i18n/setlang/`, y las URLs públicas son únicas y en español.

- **Decisión del Desarrollador:** `[x] Confirmado: Landing en "/", catálogo en "/tienda/", ficha en "/tienda/producto/<slug>-<pk>/", raíz interna movida a "/panel/" conservando name="root"`

---

## Bloque 2: Evolución del Modelo de Datos (`inventory/models.py`) y Taxonomía con IA

Actualmente [`Product`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py#L83-L145) solo almacena `raw_note`, `ai_title`, `ai_description`, `sale_price`, `status`, `is_sold` y `sold_at`.

### D2.1. Nuevos campos de catálogo y SEO en `Product` + Modelos `Category` y `StorefrontConfiguration`
Para que el escaparate funcione con las reglas ya confirmadas por el cliente (**12 categorías**, **4 estados de conservación**, **destacados**, **reservas** y **número de WhatsApp configurable**):
- **Opciones:**
  - **Opción A (Recomendada — Modelos `Category` + `StorefrontConfiguration` + Campos en `Product`):**
    1. Nuevo modelo `Category` (`name`, `slug`, `icon`, `order`, `is_active`) pre-poblado mediante migración de datos con las **12 categorías oficiales de Rápido Pack** (*Motor y accesorios, Moda y accesorios, Tecnología y electrónica, Deporte y ocio, Bicicletas, Hogar y jardín, Electrodomésticos, Cine, libros y música, Niños y bebés, Coleccionismo, Construcción y reformas, Industria y agricultura*).
    2. Nuevo modelo singleton `StorefrontConfiguration` (gestionable desde Django Admin / Panel) para guardar:
       - `whatsapp_number` (configurable sin tocar código, según requisito 5.1)
       - `store_name` (`"Rápido Pack"`), `store_address` (`"Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia"`), `opening_hours` (`"L-V 9:30–20:00 | S 10:00–15:00"`) y textos del modal *"Saber más"*.
    3. Añadir a [`Product`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py#L83-L145):
       - `category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)`
       - `condition = models.CharField(max_length=30, choices=ProductCondition.choices, blank=True, default="", db_index=True)` con las **4 etiquetas confirmadas**: `new_with_tags` (*Nuevo con etiquetas*), `very_good` (*Muy bueno*), `good` (*Buen estado*), `vintage` (*Vintage*)
       - `is_public = models.BooleanField(default=True, db_index=True)` (interruptor manual para pausar/ocultar un producto en la web pública según requisito 2.1)
       - `is_featured = models.BooleanField(default=False, db_index=True)` (para destacar productos ⭐ en portada según requisito 3.3)
       - `is_reserved = models.BooleanField(default=False, db_index=True)` (para mostrar etiqueta *"RESERVADO"* según requisito 2.3 y bloqueo de carrito en Fase 2)
  - **Opción B:** Usar un `JSONField` genérico para atributos sin columnas dedicadas.
- **Hipótesis / Recomendación (`GUESS`):** **Opción A.** Columnas explícitas indexadas (`category`, `condition`, `is_public`, `is_featured`, `is_reserved`) + `StorefrontConfiguration` cumplen el 100% de las respuestas del cliente y son ultrarrápidas de filtrar en SQLite/PostgreSQL.
- **Decisión del Desarrollador:** `[x] Opción A Confirmada (Category + StorefrontConfiguration + campos en Product)   [ ] Opción B`

### D2.2. Extracción automática de Categoría y Estado con Gemini (`ai_service.py`)
En [`inventory/services/ai_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/ai_service.py#L44-L47), `ProductListingSchema` ya usa salidas estructuradas de Pydantic con Gemini (`title`, `description`).
- **Hipótesis / Recomendación (`GUESS`):** Extender `ProductListingSchema` en [`ai_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/ai_service.py#L44-L47) para que cuando el Manager pulse **"Generar con IA"**, Gemini devuelva también `category_slug` (restringido a las 12 categorías oficiales de Rápido Pack) y `condition` (restringido a los 4 estados oficiales) en la misma llamada API (coste y latencia extra = 0).
- **Decisión del Desarrollador:**
  - [x] **Confirmado:** Extender `ProductListingSchema` en `ai_service.py` para autocompletar `category` y `condition`.
  - [x] **Backfill:** Incluir soporte opcional para clasificar productos existentes.

### D2.3. Regla de negocio exacta del QuerySet Público (`ProductQuerySet.public_visible()`)
Según lo confirmado en los puntos **2.1** y **2.2** del cuestionario del cliente:
- Mostrar automáticamente productos publicados/listos con opción de pausar (`is_public=True`).
- Mostrar los `SOLD` al final del catálogo durante **7 días** desde `sold_at` con etiqueta **"VENDIDO"** y luego ocultarlos automáticamente.
- **Hipótesis / Recomendación (`GUESS`):** Crear el método centralizado `Product.objects.public_visible()` en [`ProductQuerySet`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py#L72-L80):
  ```python
  def public_visible(self):
      seven_days_ago = timezone.now() - timedelta(days=7)
      return (
          self.filter(is_public=True, sale_price__gt=Decimal("0.00"))
          .exclude(ai_title="")
          .filter(
              models.Q(status__in=[ProductStatus.READY, ProductStatus.PUBLISHED], is_sold=False)
              | models.Q(status=ProductStatus.SOLD, is_sold=True, sold_at__gte=seven_days_ago)
          )
      )
  ```
- **Decisión del Desarrollador:**
  - [x] **Confirmado:** Usar esta lógica exacta de `public_visible()` con retención de 7 días para `SOLD`.

---

## Bloque 3: Preparación de la Arquitectura para la Fase 2 (Carrito y Pago Directo)

> **Objetivo `/idea-refine`:** No escribir código de pasarela de pago hoy, pero diseñar el esquema y las URLs de la Fase 1 para que enchufar el carrito en la Fase 2 tenga **coste de refactorización cero**.

### D3.1. Prevención de condición de carrera en artículos únicos (`stock = 1`)
En una tienda de segunda mano cada `Product` es una pieza única. En la Fase 2, si dos personas añaden el mismo abrigo al carrito, ¿cómo evitaremos el doble cobro?
- **Hipótesis / Recomendación (`GUESS`):**
  1. Incluir desde ahora en `Product` el booleano `is_reserved` (y opcionalmente `reserved_until = models.DateTimeField(null=True, blank=True)`).
  2. En la **Fase 1**, el Manager puede activar `is_reserved=True` con un clic cuando un comprador de WhatsApp dice *"me lo quedo, te hago Bizum"*. En la tienda pública se muestra el badge **"RESERVADO"** y se deshabilita la compra.
  3. En la **Fase 2**, cuando un comprador inicia una sesión de Checkout en Stripe/Redsys, el backend fija `is_reserved=True` y `reserved_until = now() + 15 min` dentro de `transaction.atomic()`. Si el webhook de pago confirma éxito $\to$ `mark_as_sold()`. Si caduca la sesión $\to$ se libera automáticamente.
- **Decisión del Desarrollador:**
  - [x] **Confirmado:** Incluir `is_reserved` y `reserved_until` desde la migración de Fase 1 para dar soporte tanto a reservas manuales por WhatsApp/Alfafar (Fase 1) como a bloqueos de checkout con Correos Express / pasarela online (Fase 2).

### D3.2. Desacoplamiento de los botones de acción (CTAs de Compra)
En la ficha pública del producto (`storefront/product_detail.html`), ¿cómo estructuramos el componente de compra para que en la Fase 2 sea trivial cambiar a "Añadir al carrito"?
- **Hipótesis / Recomendación (`GUESS`):** Aislar la caja de conversión en un partial `templates/storefront/partials/_purchase_box.html` alimentado por configuración:
  - **En Fase 1:** Renderiza el botón de WhatsApp directo (con mensaje pre-formateado y URL canónica) + modal *"Saber más"* + la lista de enlaces activos de [`ProductListingLink`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py#L505-L545) (`product.listing_links.filter(is_active=True).select_related("site")`).
  - **En Fase 2:** Ese mismo partial añade el botón primario *"🛒 Añadir al carrito / Comprar ahora"* arriba de las opciones externas.
- **Decisión del Desarrollador:** `[x] Confirmado: Aislar _purchase_box.html`

---

## Bloque 4: Seguridad, Privacidad de Datos y Protección Anti-Abuso

### D4.1. Cortafuegos de datos internos (`raw_note`, `clarifications`, `created_by`)
En [`inventory/models.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/models.py), `raw_note` puede contener anotaciones internas del tipo *"Comprado en rastro por 3€, tiene una mancha pequeña, preguntar al jefe"* y `ProductClarification` contiene conversaciones internas del equipo.
- **Hipótesis / Recomendación (`GUESS`):**
  1. En las vistas públicas, usar `.only("id", "ai_title", "ai_description", "sale_price", "status", "is_sold", "sold_at", "is_reserved", "category", "condition", "created_at")` o nunca pasar `raw_note` ni `clarifications` al contexto de la plantilla pública.
  2. Añadir un **test automatizado de seguridad** (`test_public_storefront_never_leaks_internal_notes_or_clarifications`) que verifique que ni `raw_note`, ni las dudas internas, ni los usernames del staff aparecen jamás en el HTML público ni en los metadatos JSON-LD.
- **Decisión del Desarrollador:** `[x] Confirmado: Restricción en QuerySet/Template + test de no-fuga obligatorio`

### D4.2. Canal de Contacto Público y Protección Anti-Bot (Cloudflare Turnstile)
Si además del enlace de WhatsApp incluimos un formulario web de consulta rápida (*"Preguntar por este artículo"*) o si registramos clics:
- **Hipótesis / Recomendación (`GUESS`):**
  - Para **WhatsApp (`https://wa.me/...`) y enlaces a Wallapop/Vinted**: No requieren formulario POST público o pasan por el endpoint ligero de redirección/conteo de clics.
- **Decisión del Desarrollador:**
  - [x] **Confirmado:** Enlaces a WhatsApp (`wa.me` con número configurable desde el panel) + modal *"Saber más"* + botones de Wallapop/Vinted en Fase 1 (cero formularios públicos de spam).

---

## Bloque 5: Rendimiento, Imágenes (OCI Object Storage) y Base de Datos

### D5.1. Optimización de Imágenes para el Grid Público (Miniaturas vs. Original WebP)
Actualmente [`inventory/services/image_service.py`](file:///C:/Users/Jose/antigravity/epic-tesla/inventory/services/image_service.py) convierte las fotos subidas a `.webp` (hasta 1920px) y las guarda en OCI Object Storage o disco local. Si el catálogo público muestra 20–24 productos por página, cargar 24 fotos de 1920px puede penalizar el LCP en conexiones móviles.
- **Opciones:**
  - **Opción A (MVP Rápido — Sin migración de imágenes):** Servir la `primary_image` actual con `loading="lazy"`, `decoding="async"`, dimensiones explícitas (`aspect-square object-cover`) y cabeceras `Cache-Control` largas en OCI/WhiteNoise (ya que las fotos ya están comprimidas en WebP).
  - **Opción B (Miniaturas dedicadas):** Añadir un campo `thumbnail` en `ProductImage` (ej. `480x480` WebP de ~25 KB generado en `image_service.py`) para el listado del marketplace y usar la imagen completa solo en la ficha del producto.
- **Hipótesis / Recomendación (`GUESS`):** Empezar con **Opción A** si las imágenes WebP actuales pesan <150 KB de media (usando `prefetch_related` de solo la primera imagen), o implementar **Opción B** si buscamos puntuación >95 en PageSpeed Insights móvil.
- **Decisión del Desarrollador:** `[x] Opción A Confirmada (Reutilizar WebP actual con lazy-loading y prefetch de primera imagen)`

### D5.2. SQLite vs. PostgreSQL ante tráfico público y futura Fase 2
El proyecto soporta SQLite por defecto (con backups calientes a OCI vía `backup_db.py`) y tiene perfil opcional de PostgreSQL en [`docker-compose.yml`](file:///C:/Users/Jose/antigravity/epic-tesla/docker-compose.yml).
- **Hipótesis / Recomendación (`GUESS`):**
  - En la **Fase 1**, el catálogo público realiza un **99.9% de lecturas (`SELECT`)**, donde SQLite con `journal_mode=WAL` rinde extraordinariamente bien (miles de lecturas por segundo) y mantiene operativo el sistema actual de backups a OCI (`backup_db`).
  - En la **Fase 2** (cuando haya escrituras concurrentes de carritos, bloqueos de stock y webhooks de pago), evaluar si activar `journal_mode=WAL` + `busy_timeout` en SQLite o migrar al perfil PostgreSQL de `docker-compose.yml`.
- **Decisión del Desarrollador:** `[x] Confirmado: Mantener SQLite (con WAL mode) en Fase 1`

---

## Bloque 6: Experiencia de Usuario (UX/UI), SEO y Analítica de Conversión

### D6.1. Plantilla Base Pública (`base_public.html`) vs. Plantilla Interna (`inventory/base.html`)
- **Hipótesis / Recomendación (`GUESS`):** Crear una plantilla `templates/storefront/base_public.html` totalmente independiente de `inventory/base.html`.
  - *¿Por qué?* Porque `inventory/base.html` carga scripts de Web Push (`sw.js`), badges de dudas (`❓ Dudas`), menús de `Intake`/`Dashboard` y el timestamp de compilación para empleados. La tienda pública debe tener una cabecera comercial limpia (Logo Rápido Pack, Buscador, Categorías, Selector de Idioma ES/EN), un diseño visual enfocado en conversión y un footer comercial/legal con dirección y horario de Alfafar.
- **Decisión del Desarrollador:** `[x] Confirmado: Crear base_public.html separada de inventory/base.html`

### D6.2. SEO, OpenGraph (Miniaturas al compartir por WhatsApp) y Schema.org
Cuando el cliente o un comprador comparta el enlace de un producto por WhatsApp o Instagram, o cuando Google indexe la tienda:
- **Hipótesis / Recomendación (`GUESS`):** Incluir de serie en la ficha pública:
  1. **Metaetiquetas OpenGraph (`og:title`, `og:description`, `og:image` apuntando a la foto principal, `product:price:amount`, `product:price:currency="EUR"`):** Así, al pegar el link en WhatsApp aparece la foto de la prenda, el título y el precio automáticamente.
  2. **JSON-LD `Schema.org/Product`:** Con `Offer` (`InStock` o `SoldOut` y `itemCondition: UsedCondition`) para aparecer enriquecido en Google.
  3. **`/sitemap.xml` y `/robots.txt`:** El sitemap incluye solo URLs públicas: `/`, `/tienda/`, `/tienda/categoria/<slug>/` (12), `/tienda/producto/<slug>-<pk>/` (productos de `public_visible()`), `/como-comprar/` y las páginas legales. `robots.txt` bloquea `/admin/`, `/panel/`, `/dashboard/`, `/intake/`, `/products/`, `/login/`, `/api/` y `/go/`.
  4. **Local SEO de la landing (`/`):** JSON-LD `LocalBusiness` con nombre, dirección de Alfafar, horario (`openingHoursSpecification`), teléfono y servicios (paquetería SEUR/GLS/InPost/Amazon/Kanguro/DHL, Punto Pack, tienda de segunda mano), para aparecer en búsquedas como *"punto de recogida Alfafar"*.
- **Decisión del Desarrollador:** `[x] Confirmado: Incluir OpenGraph + JSON-LD Product + sitemap.xml / robots.txt`

### D6.3. Medición de Clics de Conversión (¿Qué canal funciona mejor antes de la Fase 2?)
*Supuesto clave a validar (`/idea-refine`):* Antes de invertir en construir el carrito de la Fase 2, ¿cómo sabréis tú y el cliente cuánta gente intenta comprar desde la web y si prefieren pulsar "WhatsApp" o "Wallapop/Vinted"?
- **Hipótesis / Recomendación (`GUESS`):** Añadir un contador ligero (o modelo `ProductClickEvent` / campo `views_count` + `outbound_clicks`) o ruta intermedia `/go/link/<link_pk>/` y `/go/whatsapp/<product_pk>/` que incremente un contador en base de datos antes de redirigir a Wallapop/Vinted/WhatsApp, mostrándolo en el Dashboard del Manager.
- **Decisión del Desarrollador:**
  - [x] **Opción A Confirmada:** Añadir redirección con conteo de clics (WhatsApp vs. Wallapop/Vinted) visible en el panel del Manager sin depender de cookies de terceros.

---

## Resumen de Decisiones Rápidas para el Desarrollador (Checklist Pre-PRD — 100% Confirmado)

| # | Decisión Arquitectónica | Recomendación por Defecto | Estado |
| :--- | :--- | :--- | :--- |
| **1** | Organización del código | Nueva app `storefront/` consumiendo `inventory.models` | `[x] Aceptado` |
| **2** | URLs públicas | `/` (Landing de negocio), `/tienda/` (Catálogo), `/tienda/categoria/<slug>/`, `/tienda/producto/<slug>-<pk>/` (Ficha); raíz interna movida a `/panel/` (`name="root"`); `/dashboard/` e `/intake/` sin cambios | `[x] Aceptado (actualizado)` |
| **3** | Taxonomía e IA | Modelo `Category` (12 categorías) + `StorefrontConfiguration` + `condition` (4 estados) auto-extraídos por Gemini | `[x] Aceptado` |
| **4** | Puente a Fase 2 (Carrito) | Campos `is_reserved` / `reserved_until` + partial `_purchase_box.html` desacoplado | `[x] Aceptado` |
| **5** | Seguridad y Privacidad | `public_visible()` QuerySet (7 días para `SOLD`) + prohibición estricta de exponer `raw_note` y `clarifications` | `[x] Aceptado` |
| **6** | SEO y WhatsApp Preview | OpenGraph completo + JSON-LD `Product` + `robots.txt` + páginas legales estándar | `[x] Aceptado` |
| **7** | Analítica de conversión | Conteo propio de clics hacia WhatsApp y enlaces de Wallapop/Vinted | `[x] Aceptado` |
