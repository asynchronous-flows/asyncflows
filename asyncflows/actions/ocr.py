import os

from asyncflows import Action, BaseModel
from asyncflows.models.io import BlobRepoInputs
from asyncflows.models.file import File


class Inputs(BlobRepoInputs):
    pdf: File | str


class Outputs(BaseModel):
    pdf_ocr: str


class OCR(Action[Inputs, Outputs]):
    name = "ocr"

    async def run(self, inputs: Inputs) -> Outputs:
        import ocrmypdf

        if isinstance(inputs.pdf, str):
            filepath = inputs.pdf
        else:
            filepath = await inputs.pdf.download_file(
                self.log,
                self.temp_dir,
                inputs._blob_repo,
            )

        ocr_filepath = os.path.join(self.temp_dir, "ocr.pdf")

        # TODO find async alternative for this
        ocrmypdf.ocr(filepath, ocr_filepath)

        return Outputs(
            pdf_ocr=ocr_filepath,
        )
