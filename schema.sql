CREATE TABLE IF NOT EXISTS misiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL CHECK (length(nombre) BETWEEN 1 AND 120),
    destino TEXT NOT NULL CHECK (length(destino) BETWEEN 1 AND 100),
    fecha TEXT NOT NULL DEFAULT '' CHECK (
        fecha = '' OR (length(fecha) = 10 AND fecha GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')
    ),
    estado TEXT NOT NULL DEFAULT 'Planificada'
        CHECK (estado IN ('Planificada', 'En curso', 'Completada')),
    notas TEXT NOT NULL DEFAULT '' CHECK (length(notas) <= 2000),
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
