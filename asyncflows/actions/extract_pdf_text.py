import pypdfium2 as pdfium

from asyncflows.actions.base import Action, CacheControlOutputs, BlobRepoInputs
from asyncflows.models.file import File


class Inputs(BlobRepoInputs):
    file: File | str
    min_start_chars: int = 1000


class Outputs(CacheControlOutputs):
    start_of_text: str | None = None
    full_text: str | None = None


class ExtractPdfText(Action[Inputs, Outputs]):
    name = "extract_pdf_text"

    async def run(self, inputs: Inputs) -> Outputs:
        if isinstance(inputs.file, str):
            filepath = inputs.file
        else:
            filepath = await inputs.file.download_file(
                self.log, self.temp_dir, inputs._blob_repo
            )
            if filepath is None:
                self.log.error("Failed to download file")
                return Outputs(
                    _cache=False,
                )

        # TODO make this async, tho it's relatively fast
        pdf = pdfium.PdfDocument(filepath)
        if len(pdf) == 0:
            raise Exception("PDF has no pages")

        full_text = ""
        start_of_text = ""
        for page in pdf:
            page_text = page.get_textpage().get_text_range()
            full_text += page.get_textpage().get_text_range() + "\n\n"
            if len(start_of_text) < inputs.min_start_chars:
                start_of_text += page_text

        return Outputs(
            start_of_text=start_of_text,
            full_text=full_text,
        )
