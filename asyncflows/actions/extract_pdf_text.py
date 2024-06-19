from asyncflows.models.io import (
    CacheControlOutputs,
    BlobRepoInputs,
)
from asyncflows import Action, BaseModel

from asyncflows.models.file import File


class Inputs(BlobRepoInputs):
    file: File | str
    min_start_chars: int = 1000


class Page(BaseModel):
    text: str
    page_number: int
    title: str


class Outputs(CacheControlOutputs):
    title: str | None = None
    start_of_text: str | None = None
    full_text: str | None = None
    pages: list[Page] | None = None


class ExtractPdfText(Action[Inputs, Outputs]):
    name = "extract_pdf_text"

    async def run(self, inputs: Inputs) -> Outputs:
        import pypdfium2 as pdfium

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

        title = filepath.rsplit("/", 1)[-1].rsplit(".", 1)[0]

        start_of_text = ""
        page_texts = []
        for page in pdf:
            page_text = page.get_textpage().get_text_range()
            page_texts.append(page_text)
            if len(start_of_text) < inputs.min_start_chars:
                start_of_text += page_text

        full_text = "\n\n".join(page_texts)

        pages = [
            Page(
                text=page_text,
                page_number=i + 1,
                title=title,
            )
            for i, page_text in enumerate(page_texts)
        ]

        return Outputs(
            title=title,
            start_of_text=start_of_text,
            full_text=full_text,
            pages=pages,
        )
