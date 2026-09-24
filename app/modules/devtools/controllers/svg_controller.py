"""HTTP-facing logic for the svg-optimizer and svg-generator tools."""

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.modules.devtools.controllers.devtools_controller_helpers import (
    as_http_error,
    read_upload,
)
from app.modules.devtools.services.svg_generator_service import svg_generator_service
from app.modules.devtools.services.svg_optimizer_service import svg_optimizer_service


class SvgController:
    async def optimize_svg(self, file: UploadFile, precision: int = 2) -> dict:
        svg_data = await read_upload(file, "svg")
        try:
            result = svg_optimizer_service.optimize_svg(
                svg_data,
                precision=precision,
            )
        except (OSError, ValueError) as error:
            raise as_http_error("Unable to optimize SVG", error) from error
        return {
            "success": True,
            "data": result["data"],
            "original_size": result["original_size"],
            "minified_size": result["minified_size"],
            "saved_percent": round(
                (1 - result["minified_size"] / max(1, result["original_size"]))
                * 100,
                1,
            ),
        }

    async def svg(
        self,
        image: UploadFile,
        threshold: int = 128,
        background_color: str = "white",
        foreground_color: str = "black",
    ) -> tuple[bytes, str]:
        image_data = await read_upload(image, "image")
        try:
            svg_text = await run_in_threadpool(
                svg_generator_service.generate_svg,
                image_data,
                threshold=threshold,
                background_color=background_color,
                foreground_color=foreground_color,
            )
        except (OSError, ValueError, RuntimeError) as error:
            raise as_http_error("Unable to generate SVG", error) from error
        return svg_text.encode("utf-8"), "image/svg+xml"


svg_controller = SvgController()
