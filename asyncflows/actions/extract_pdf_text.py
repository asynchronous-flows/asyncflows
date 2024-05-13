import ocrmypdf
import pypdfium2 as pdfium

from asyncflows.actions.base import Action, CacheControlOutputs, BlobRepoInputs
from asyncflows.models.file import File


class Inputs(BlobRepoInputs):
    file: File | str
    min_start_chars: int = 1000
    ocr: bool = True


class Outputs(CacheControlOutputs):
    start_of_text: str | None = None
    full_text: str | None = None
    pages: list[str] | None = None


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

        # ocr the pdf
        if inputs.ocr:
            ocr_filepath = filepath + ".ocr.pdf"
            # TODO find async alternative for this
            ocrmypdf.ocr(filepath, ocr_filepath)
            filepath = ocr_filepath

        # TODO make this async, tho it's relatively fast
        pdf = pdfium.PdfDocument(filepath)
        if len(pdf) == 0:
            raise Exception("PDF has no pages")

        start_of_text = ""
        pages = []
        for page in pdf:
            page_text = page.get_textpage().get_text_range()
            pages.append(page_text)
            if len(start_of_text) < inputs.min_start_chars:
                start_of_text += page_text

        full_text = "\n\n".join(pages)

        return Outputs(
            start_of_text=start_of_text,
            full_text=full_text,
            pages=pages,
        )
