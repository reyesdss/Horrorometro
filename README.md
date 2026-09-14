# Horrorómetro

Página estática para GitHub Pages. Incluye el ranking personal de 91 películas, series/episodios, bestiario y V/H/S.

## Publicar
1. Sube el contenido de esta carpeta a un repositorio de GitHub.
2. Activa GitHub Pages desde Settings → Pages → Deploy from branch.
3. La página no necesita una API key para funcionar. Las portadas se intentan localizar automáticamente mediante la API pública de MediaWiki/Wikipedia desde el navegador y se almacenan en caché local.

## Añadir una película
Edita `peliculas.csv` y vuelve a regenerar `data/catalog.json` si necesitas actualizar la web. Para una versión sencilla, puedes editar directamente `data/catalog.json` siguiendo la estructura existente.

## Nota
Las calificaciones personales provienen del ranking aportado por el autor. Los ratings externos de series/episodios se muestran solo como referencia.
