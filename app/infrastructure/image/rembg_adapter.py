import importlib.util
import os
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from app.core.config import settings

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"

# Input the U2-Net family of models (u2net, u2netp, silueta) is trained on.
_MODEL_INPUT_SIZE = (320, 320)
_MODEL_MEAN = (0.485, 0.456, 0.406)
_MODEL_STD = (0.229, 0.224, 0.225)
_UNAVAILABLE = (
    "Background removal requires the 'rembg' package. "
    "It is not available in this environment."
)


class RemBGAdapter:
    """Background removal through rembg, or onnxruntime on its own.

    rembg pulls in scipy, scikit-image and numba and peaks near 800 MB of
    memory, more than small hosts allow. When it is not installed the
    bundled model is run directly with onnxruntime, which follows the
    same steps in roughly half the memory.
    """

    def __init__(self) -> None:
        self._session = None
        self._direct_session = None

    def _get_session(self):
        if self._session is None:
            try:
                from rembg import new_session
            except ImportError:
                raise RuntimeError(_UNAVAILABLE)
            if (MODELS_DIR / f"{settings.rembg_model}.onnx").exists():
                os.environ["U2NET_HOME"] = str(MODELS_DIR)
            self._session = new_session(settings.rembg_model)
        return self._session

    def _get_direct_session(self):
        if self._direct_session is None:
            model = MODELS_DIR / f"{settings.rembg_model}.onnx"
            try:
                import onnxruntime
            except ImportError:
                raise RuntimeError(_UNAVAILABLE)
            if not model.exists():
                raise RuntimeError(_UNAVAILABLE)
            options = onnxruntime.SessionOptions()
            # The arena keeps every buffer it ever allocated; without it
            # memory is returned once an image is done.
            options.enable_cpu_mem_arena = False
            options.intra_op_num_threads = min(2, os.cpu_count() or 1)
            options.inter_op_num_threads = 1
            self._direct_session = onnxruntime.InferenceSession(
                str(model),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
        return self._direct_session

    def remove_background(self, image: Image.Image) -> Image.Image:
        if importlib.util.find_spec("rembg") is None:
            return self._remove_background_directly(image)
        try:
            from rembg import remove
        except ImportError:
            raise RuntimeError(_UNAVAILABLE)
        output = remove(image, session=self._get_session())
        if isinstance(output, Image.Image):
            return output
        buffer = BytesIO(output)
        try:
            loaded = Image.open(buffer)
            loaded.load()
            return loaded
        finally:
            buffer.close()

    def _remove_background_directly(self, image: Image.Image) -> Image.Image:
        import numpy

        session = self._get_direct_session()
        image = ImageOps.exif_transpose(image)
        pixels = numpy.asarray(
            image.convert("RGB").resize(_MODEL_INPUT_SIZE, Image.Resampling.LANCZOS),
            dtype=numpy.float32,
        )
        pixels = pixels / max(float(pixels.max()), 1e-6)
        pixels = (pixels - numpy.array(_MODEL_MEAN, dtype=numpy.float32)) / numpy.array(
            _MODEL_STD, dtype=numpy.float32
        )
        batch = pixels.transpose(2, 0, 1)[numpy.newaxis].astype(numpy.float32)

        prediction = session.run(None, {session.get_inputs()[0].name: batch})[0][0, 0]
        low, high = float(prediction.min()), float(prediction.max())
        prediction = (prediction - low) / max(high - low, 1e-6)
        mask = Image.fromarray(
            (prediction.clip(0, 1) * 255).astype("uint8"),
            mode="L",
        ).resize(image.size, Image.Resampling.LANCZOS)

        return Image.composite(
            image.convert("RGBA"),
            Image.new("RGBA", image.size, 0),
            mask,
        )

    def remove_background_to_png(
        self,
        image: Image.Image,
    ) -> bytes:
        result = self.remove_background(image)
        output = BytesIO()
        try:
            result.save(
                output,
                format="PNG",
            )
            return output.getvalue()
        finally:
            output.close()


rembg_adapter = RemBGAdapter()
