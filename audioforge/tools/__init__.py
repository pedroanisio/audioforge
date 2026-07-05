"""AudioForge developer tooling — generators and drift gates.

Not part of the shipped runtime surface: these modules regenerate or drift-check
committed artifacts that are derived from the engine's source of truth (e.g.
``docs/ir.schema.json`` from :func:`audioforge.ir_schema.ir_json_schema`). They
are the AudioForge analog of a ``tooling/`` directory and are invoked via
``python -m audioforge.tools.<name>`` and the ``make`` gates.
"""
