# Prompts para Google Stitch — Diseño UI/UX de Rápido Pack (`rapidopack.es`)

> **Consejo para Google Stitch:**  
> Google Stitch genera mejores estructuras de layout y jerarquía visual cuando las instrucciones técnicas del prompt están en **inglés**, especificando explícitamente que **todos los textos visibles en pantalla (UI copy) estén en español**. Abajo tienes tanto el **Prompt Maestro optimizado (Inglés con textos UI en Español)** como la **versión 100% en Español**, además de un segundo prompt opcional para la **Ficha de Producto y Modal "Saber más"**.

---

## 1. Prompt Maestro para el Catálogo de la Tienda (`/tienda/`) — *Recomendado para copiar y pegar en Google Stitch*

> **Nota (mapa de URLs actualizado):** Este diseño corresponde ahora a **`rapidopack.es/tienda/`**. La raíz `rapidopack.es/` es la **landing corporativa** (ver sección 4). En el diseño de Stitch, el logo debe enlazar a la landing y el menú debe incluir "Paquetería", "Punto Pack", "Tienda" y "Contacto".

```text
Design a modern, high-converting, responsive e-commerce marketplace homepage for "Rápido Pack" (rapidopack.es), a curated secondhand, vintage, and opportunity goods store with both an online catalog and a physical pickup store in Alfafar, Valencia (Spain). All visible UI text, labels, and badges MUST be in Spanish.

### 1. Visual Style & Aesthetic
- Aesthetic: Clean, trustworthy, modern marketplace blending the best of Vinted, Wallapop, and BackMarket.
- Color Palette: Warm off-white/light slate background (#F8FAFC), deep charcoal text (#0F172A), primary brand accent in vibrant Emerald/Teal (#0D9488) for trust and sustainability, and secondary warm Amber/Orange (#F59E0B) for "Destacado" (Featured) and "Reservado" badges. WhatsApp green (#25D366) for direct contact actions.
- Typography: Inter or Plus Jakarta Sans. Crisp hierarchy, high readability, bold Euro prices (e.g., "45,00 €"), minimum 16px inputs.

### 2. Top Utility Bar & Main Header (Sticky)
- Top Announcement Bar (compact dark slate):
  "📍 Tienda física y recogida GRATIS en Carrer del Comte Ronrée, 8, Alfafar (Valencia) | 🕒 L-V 9:30–20:00 · Sáb 10:00–15:00 | 📦 Envíos seguros vía Wallapop y Vinted"
- Main Header:
  - Left: Bold brand logo "Rápido Pack" with a subtle box/lightning icon and subtitle badge "rapidopack.es".
  - Center: Large, prominent pill-shaped search bar: "Buscar artículos, marcas, categorías..." with a search icon button.
  - Right: Language switcher pill ("ES | EN"), a "📍 Cómo comprar / Saber más" ghost button, and a primary WhatsApp contact chip ("💬 Contacto directo").

### 3. Compact Hero & Trust Strip (Above the Fold — Marketplace-First)
- Keep the hero compact so the product catalog is immediately visible above the fold.
- Headline: "Tu tienda de segunda mano y oportunidad en Valencia y online"
- Subtitle: "Artículos únicos revisados al detalle. Recoge gratis en nuestra tienda de Alfafar o compra con envío protegido."
- 4 Trust Badges inside the banner:
  1. "✅ Artículos revisados y verificados"
  2. "📸 Fotos 100% reales del producto exacto"
  3. "🏪 Recogida gratuita en tienda (Alfafar)"
  4. "💬 Trato directo por WhatsApp o vía Wallapop/Vinted"

### 4. Horizontal Scrollable Category Rail (12 Official Categories)
- Clean horizontal pill/icon bar right below the hero with "Todo (Activo)" selected, followed by the 12 official categories:
  1. Motor y accesorios
  2. Moda y accesorios
  3. Tecnología y electrónica
  4. Deporte y ocio
  5. Bicicletas
  6. Hogar y jardín
  7. Electrodomésticos
  8. Cine, libros y música
  9. Niños y bebés
  10. Coleccionismo
  11. Construcción y reformas
  12. Industria y agricultura

### 5. Filter & Sorting Toolbar
- Left/Center filter pills & dropdowns:
  - Price Range filter ("Rango de precio"): Quick chips "Todos", "Menos de 20 €", "20 € – 50 €", "Más de 50 €".
  - Condition filter ("Estado"): Multi-select pills showing the 4 official condition states:
    - "Nuevo con etiquetas"
    - "Muy bueno"
    - "Buen estado"
    - "Vintage"
- Right side:
  - Results counter: "142 artículos disponibles"
  - Sort dropdown ("Ordenar por"): "Novedades primero" (selected), "Destacados ⭐", "Precio: menor a mayor", "Precio: mayor a menor".

### 6. Marketplace Product Grid (4 columns on Desktop, 2 on Mobile)
Display 8 realistic secondhand/opportunity product cards with 1:1 square product photos, demonstrating the 4 distinct product lifecycle states:

- Card Structure:
  - 1:1 square image container with rounded corners.
  - Top-left badge (when applicable): "⭐ DESTACADO" (Amber badge), "⏳ RESERVADO" (Orange badge), or "VENDIDO" (Red/Slate badge).
  - Top-right badge: Condition pill ("Nuevo con etiquetas", "Muy bueno", "Buen estado", or "Vintage").
  - Card body:
    - Small muted category label + reference (e.g., "Tecnología y electrónica · Ref. #1042").
    - 2-line truncated product title (e.g., "Bicicleta de Montaña Orbea MX 29 Aluminio", "Cámara Retro Canon AE-1 Program 50mm", "Taladro Percutor Bosch Professional 18V").
    - Bold large price in Euros (e.g., "185,00 €").
    - Conversion row at the bottom of the card:
      - Primary button: "💬 WhatsApp" (direct inquiry/reservation) + subtle info link "Saber más".
      - Secondary mini badges showing where it is also listed: "Wallapop" and "Vinted" pills.

- Include these specific visual state variations in the grid:
  - First 2 cards: Marked with "⭐ DESTACADO" badge pinned at the top of the grid.
  - Next 4 cards: Standard available items across diverse categories (Motor, Bicicletas, Electrodomésticos, Coleccionismo, Moda).
  - 1 card in "⏳ RESERVADO" state: Shows an amber "RESERVADO" badge over the photo and a disabled button "Reservado temporalmente".
  - Last 1 card in "VENDIDO" state (Social Proof): Placed at the end of the grid with a slightly dimmed photo, a clear "VENDIDO" stamp badge, and "Vendido recientemente" label to demonstrate active store turnover.

### 7. Pagination & Footer
- Clean pagination controls below the grid ("Anterior · Página 1 de 8 · Siguiente").
- Comprehensive commercial footer with 3 columns:
  - Column 1 (Brand & Physical Store): "Rápido Pack (rapidopack.es)", address "Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia", opening hours "Lunes a Viernes: 9:30 a 20:00 h | Sábados: 10:00 a 15:00 h", and "Recogida gratuita en local".
  - Column 2 (Categorías Principales): Links to the main categories.
  - Column 3 (Legal & Ayuda): "¿Cómo comprar? (Saber más)", "Aviso Legal", "Política de Privacidad", "Política de Cookies".
```

---

## 2. Versión del Prompt 100% en Español (Alternativa para Google Stitch)

```text
Diseña la portada (homepage) responsive de un marketplace moderno de segunda mano y oportunidad llamado "Rápido Pack" (rapidopack.es), con tienda física en Alfafar (Valencia) y catálogo online.

1. ESTILO VISUAL:
- Inspirado en Vinted, Wallapop y BackMarket: limpio, rápido, confiable y centrado en la fotografía del producto.
- Fondo claro (#F8FAFC), textos oscuros de alto contraste (#0F172A), color principal Verde Esmeralda/Teal (#0D9488), acentos en Ámbar (#F59E0B) para "Destacados" y "Reservados", y Verde WhatsApp (#25D366) para el contacto directo.

2. CABECERA Y BARRA SUPERIOR:
- Barra superior informativa: "📍 Recogida GRATIS en tienda: Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia | 🕒 L-V 9:30–20:00 · Sáb 10:00–15:00 | 📦 Envíos por Wallapop y Vinted".
- Header principal con el logo "Rápido Pack", un buscador central grande ("Buscar artículos, categorías, modelos..."), selector de idioma ("ES | EN") y botón "¿Cómo comprar? / Saber más".

3. BANNER DE CONFIANZA COMPACTO:
- Título: "Tu tienda de segunda mano y oportunidad en Alfafar (Valencia) y online".
- 4 sellos de garantía: "✅ Productos revisados", "📸 Fotos 100% reales", "🏪 Recogida gratis en Alfafar", "💬 Trato directo por WhatsApp o vía Wallapop/Vinted".

4. CARRUSEL HORIZONTAL DE 12 CATEGORÍAS:
- Botones tipo píldora con iconos: Todo (Activo), Motor y accesorios, Moda y accesorios, Tecnología y electrónica, Deporte y ocio, Bicicletas, Hogar y jardín, Electrodomésticos, Cine libros y música, Niños y bebés, Coleccionismo, Construcción y reformas, Industria y agricultura.

5. BARRA DE FILTROS Y ORDENACIÓN:
- Filtro por Rango de Precio (€): Todos, < 20 €, 20 € – 50 €, > 50 €.
- Filtro por Estado de conservación (4 etiquetas oficiales): "Nuevo con etiquetas", "Muy bueno", "Buen estado", "Vintage".
- Selector de ordenación a la derecha: "Novedades primero" (por defecto), "Destacados ⭐", "Precio: menor a mayor", "Precio: mayor a menor".

6. GRID DE PRODUCTOS (4 columnas en escritorio, 2 en móvil):
- Tarjetas con foto cuadrada 1:1, etiqueta de estado arriba a la derecha ("Nuevo con etiquetas", "Muy bueno", "Buen estado" o "Vintage"), categoría, referencia (ej. "Ref. #1042"), título en 2 líneas y precio grande en Euros (ej. "65,00 €").
- Pie de cada tarjeta con botón principal "💬 WhatsApp", enlace "Saber más" e indicadores de disponible en "Wallapop" / "Vinted".
- Mostrar variedad de estados en el grid:
  - 2 primeros productos con etiqueta "⭐ DESTACADO".
  - 1 producto con etiqueta "⏳ RESERVADO" y botón deshabilitado.
  - 1 producto al final del listado con sello "VENDIDO" (prueba social de los últimos 7 días).

7. PIE DE PÁGINA (FOOTER):
- Datos de la tienda física en Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia, horario comercial (L-V 9:30-20:00, S 10:00-15:00) y enlaces legales (Aviso Legal, Privacidad, Cookies).
```

---

## 3. Prompt Complementario (Opcional): Ficha de Producto + Modal "Saber más"

Si después de generar la portada quieres pedirle a Google Stitch la vista de detalle del producto, usa este prompt:

```text
Design the Product Detail Page and the "Saber más" (How to Buy) info modal for the "Rápido Pack" (rapidopack.es) secondhand marketplace, matching the homepage style. All UI text in Spanish.

- Left Column (60%): Large 1:1 main product photo with zoom icon and a row of 5 WebP thumbnail images underneath.
- Right Column (40% - Sticky Purchase Box):
  - Breadcrumb: Inicio > Tecnología y electrónica > Ref. #1042
  - Badges row: "⭐ DESTACADO", Condition badge "Muy bueno", and availability badge "Disponible (Pieza única)".
  - Product Title and large Euro price: "145,00 €" (Precio único en tienda y plataformas).
  - Primary CTA Button (Full width, vibrant WhatsApp Green): "💬 Comprar / Consultar por WhatsApp" with subtext "Mensaje automático con la Ref. #1042 listo para enviar".
  - Secondary Link right below: "ℹ️ Saber más sobre recogida gratis en Alfafar y envíos".
  - External Marketplace Section ("También disponible con envío directo en:"): Official styled outbound buttons for "Comprar en Wallapop" and "Comprar en Vinted".
  - Trust & Pickup Card:
    - "🏪 Recogida GRATIS en tienda: Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia (L-V 9:30–20:00, Sáb 10:00–15:00). Pagos en tienda o trato directo: Efectivo, Bizum o Transferencia."
    - "📦 Envíos a domicilio: Gestionados con envío seguro a través de nuestras fichas en Wallapop y Vinted."
  - Structured AI Description section with clean bullet points detailing features, measurements, and honest condition notes.
```


---

## 4. Prompt para Landing Page Corporativa (`/` — Negocio completo: Punto Pack + Paquetería + Tienda)

> **Identidad de marca propuesta para Rápido Pack** (usada en el prompt, validar con el cliente):
> - **Concepto:** Rápido Pack es el *punto de barrio* de Alfafar donde se envía, recibe y devuelve paquetería de las principales agencias, y donde además se descubren artículos de segunda mano y oportunidad revisados. Dos negocios, una misma promesa: **rapidez y confianza a la vuelta de la esquina**.
> - **Significado del nombre:** *Rápido* = gestiones en minutos, sin colas ni complicaciones. *Pack* = el paquete, tanto el que envías o recoges como el artículo que compras.
> - **Pilares:** Rapidez · Cercanía (comercio local de Alfafar) · Confianza (artículos revisados, gestión segura del paquete) · Segunda vida (consumo sostenible).
> - **Tono de voz:** Cercano, directo y resolutivo; tuteo; frases cortas; cero tecnicismos.
> - **Visual:** Verde esmeralda/teal (confianza y sostenibilidad), ámbar (energía/rapidez), fondo claro y limpio; logo con caja + flecha/rayo de movimiento.

```text
Design a modern, responsive business landing page for "Rápido Pack" (rapidopack.es), a local neighborhood shop in Alfafar, Valencia (Spain) that combines two services under one brand: (1) a multi-carrier parcel point for sending, receiving and returning packages, and (2) a curated secondhand and opportunity goods store with an online catalog. All visible UI text MUST be in Spanish. Use a friendly, direct tone (informal "tú").

### Brand Identity & Visual Style
- Brand promise: "Rapidez y confianza a la vuelta de la esquina."
- Brand pillars: Rapidez, Cercanía, Confianza, Segunda vida.
- Logo: bold wordmark "Rápido Pack" with a simple parcel box icon combined with a motion arrow/lightning stroke.
- Colors: light background (#F8FAFC), deep charcoal text (#0F172A), primary Emerald/Teal (#0D9488), energetic Amber accent (#F59E0B) for highlights and "Nuevo" badges, WhatsApp green (#25D366) for contact buttons.
- Typography: Plus Jakarta Sans or Inter, bold headings, generous whitespace, rounded cards (16px radius), soft shadows, friendly line icons.

### 1. Sticky Header
- Left: "Rápido Pack" logo.
- Center nav links: "Paquetería", "Punto Pack", "Tienda", "Sobre nosotros", "Contacto".
- Right: language pill "ES | EN" and primary button "💬 Escríbenos por WhatsApp".

### 2. Hero Section (split layout)
- Left:
  - Small amber eyebrow badge: "📍 Tu punto de confianza en Alfafar"
  - Headline: "Envía, recibe y descubre. Todo en un mismo sitio."
  - Subtitle: "Somos punto de paquetería multimarca y Punto Pack, y además tenemos una tienda de segunda mano con artículos revisados. Rápido, cerca y sin complicaciones."
  - Two CTAs: primary "Ver servicios de paquetería" and secondary outline "Explorar la tienda".
  - Small info line: "🕒 L–V 9:30–20:00 · Sáb 10:00–15:00"
- Right: bright, welcoming illustration or photo of a modern local shop counter with neatly stacked parcels on one side and curated secondhand items (bike, retro camera, small appliance) on the other.

### 3. Carrier Logo Strip ("Trabajamos con")
- Horizontal row of clean, equally sized carrier name chips/logos in grayscale that turn colored on hover: "SEUR", "GLS", "InPost", "Amazon", "Kanguro", "DHL", plus a highlighted chip "Punto Pack".
- Caption: "Gestionamos tus envíos, recogidas y devoluciones de las principales agencias."

### 4. Parcel Services Section ("Servicios de paquetería")
- Title: "Tu paquete, en buenas manos"
- 4 service cards with icons:
  1. "📦 Envíos" – "Trae tu paquete y lo enviamos con la agencia que necesites."
  2. "📥 Recepción y recogida" – "Recibe tus pedidos aquí y recógelos cuando te venga bien, sin esperar en casa."
  3. "↩️ Devoluciones" – "Gestiona tus devoluciones de Amazon y otras tiendas online en minutos."
  4. "🏪 Punto Pack" – "Somos Punto Pack oficial: deja o recoge tus envíos de forma rápida y segura."
- Below the cards, a 3-step horizontal "Cómo funciona" strip: "1. Trae tu paquete o código" → "2. Lo gestionamos al momento" → "3. Listo, con seguimiento".

### 5. Brand Identity Section ("Quiénes somos")
- Split layout: left a warm photo of the shop team/storefront in Alfafar; right text block.
- Title: "Más que una tienda, tu punto de barrio"
- Paragraph: "Rápido Pack nace en Alfafar con una idea sencilla: que enviar, recibir o comprar sea rápido y de confianza. 'Rápido' porque valoramos tu tiempo. 'Pack' porque cada paquete, ya sea el que envías o el artículo que te llevas, merece el mismo cuidado."
- 4 value pills/cards with icons:
  - "⚡ Rapidez" – "Gestiones en minutos, sin colas."
  - "🤝 Cercanía" – "Comercio local, trato directo y personal."
  - "✅ Confianza" – "Artículos revisados y paquetes bien custodiados."
  - "♻️ Segunda vida" – "Damos una nueva oportunidad a productos con historia."

### 6. Featured Products Section ("Lo último en nuestra tienda")
- Title: "Recién llegados" with subtitle "Los 4 artículos más nuevos de nuestra tienda. Piezas únicas: cuando se van, no vuelven."
- Right-aligned link: "Ver toda la tienda →"
- 4-column product card grid (2 columns on mobile), each card:
  - 1:1 square product photo with rounded corners.
  - Top-left amber badge "🆕 NUEVO".
  - Top-right condition pill (one of: "Nuevo con etiquetas", "Muy bueno", "Buen estado", "Vintage").
  - Muted category + reference line (e.g., "Bicicletas · Ref. #1051").
  - 2-line product title, e.g.:
    - "Bicicleta de Montaña Orbea MX 29 Aluminio" – "185,00 €" – Muy bueno
    - "Cámara Retro Canon AE-1 Program 50mm" – "120,00 €" – Vintage
    - "Taladro Percutor Bosch Professional 18V" – "65,00 €" – Buen estado
    - "Cafetera Superautomática De'Longhi Magnifica" – "149,00 €" – Nuevo con etiquetas
  - Bold Euro price.
  - Full-width green button "💬 Consultar por WhatsApp" and small text link "Saber más".

### 7. Why Choose Us / Trust Stats
- 4 stat blocks in a teal band: "+6 agencias de paquetería", "Punto Pack oficial", "Recogida gratis de compras en tienda", "Artículos 100% revisados".

### 8. Location & Contact Section ("Visítanos")
- Left: embedded map placeholder pinned at "Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia".
- Right card:
  - "📍 Carrer del Comte Ronrée, 8, 46910 Alfafar, Valencia"
  - "🕒 Lunes a Viernes: 9:30 – 20:00 h | Sábados: 10:00 – 15:00 h | Domingos: cerrado"
  - Buttons: "💬 Escríbenos por WhatsApp" and outline "Cómo llegar".

### 9. Final CTA Banner
- Teal gradient banner: "¿Tienes un paquete o buscas una oportunidad? Te esperamos en Alfafar."
- Buttons: "Ver la tienda online" and "Escríbenos por WhatsApp".

### 10. Footer
- Column 1: "Rápido Pack" logo, short tagline "Rapidez y confianza a la vuelta de la esquina.", address and hours.
- Column 2 "Servicios": Envíos, Recepción de paquetes, Devoluciones, Punto Pack, Tienda de segunda mano.
- Column 3 "Agencias": SEUR, GLS, InPost, Amazon, Kanguro, DHL.
- Column 4 "Legal": Aviso Legal, Política de Privacidad, Política de Cookies.
- Bottom bar: "© 2026 Rápido Pack · rapidopack.es".
```
