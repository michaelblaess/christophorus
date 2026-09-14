"""Die Auswahl des Exporters zu einem Format.

Die Oberflaeche ruft nur `write_export()`. Die Importe der Exporter stehen
bewusst in der Funktion: openpyxl ist schwer, und wer nur nach JSON schreibt,
soll nicht darauf warten.
"""

from pathlib import Path

from death_proof.models.export_format import ExportFormat
from death_proof.models.export_job import ExportJob


def write_export(export_format: ExportFormat, job: ExportJob, out_path: Path) -> None:
    """Schreibt den Auftrag im gewaehlten Format.

    Args:
        export_format: Das Ausgabeformat.
        job: Was exportiert werden soll.
        out_path: Der Zielpfad.

    Raises:
        ValueError: Wenn zu dem Format kein Exporter bekannt ist.
    """
    if export_format.key == "excel":
        from death_proof.services.excel_export import export_trips

        export_trips(
            trips=job.trips,
            out_path=out_path,
            title_line1=job.title,
            subtitle=job.subtitle,
            group_by_month=job.group_by_month,
            category_labels=job.category_labels,
        )
        return

    if export_format.key == "json":
        from death_proof.services.json_export import export_json

        export_json(job, out_path)
        return

    if export_format.key == "markdown":
        from death_proof.services.markdown_export import export_markdown

        export_markdown(job, out_path)
        return

    raise ValueError(f"Kein Exporter fuer Format {export_format.key}")
