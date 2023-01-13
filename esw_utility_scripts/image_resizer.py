import logging
import os
import time
from argparse import ArgumentParser, Namespace

import pytomlpp
from PIL import Image, UnidentifiedImageError

# Configure logger
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def convert_config_values(config: dict) -> dict:
    new_paths = []
    # Convert strftime variables
    for path in config["paths"]:
        new_paths.append(time.strftime(path))
    config["paths"] = new_paths
    return config


def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    return args


def calulate_proprotional_change(
    old_size: int, new_size: int, second_dimension: int
) -> int:
    return int(new_size / old_size * second_dimension)


def main():
    args = parse_args()
    with open(args.config) as f:
        config = convert_config_values(pytomlpp.load(f))
    for path in config.get("paths", []):
        if not os.path.exists(path):
            logger.warning(f"Path '{path}' was skipped as it doesn't exist.")
            continue
        with os.scandir(path) as scan_results:
            # noinspection PyTypeChecker
            for item in scan_results:
                # We neither want dirs nor symlinks
                if not item.is_file(follow_symlinks=False):
                    logger.debug(f"Skipped '{item.path}' as it's not a file.")
                    continue
                elif time.time() - item.stat().st_mtime > config["max_age"] * 60:
                    logger.debug(f"Skipped '{item.path}' as it's too old.")
                    continue
                # Ignore files which end with the new_image suffix to prevent recursion
                elif item.path.rsplit(".", 1)[0].endswith(
                    config["new_image"]["suffix"]
                ):
                    logger.debug(
                        f"Skipped '{item.path}' as it's ending with new image suffix."
                    )
                    continue
                # First check if the file is an uncorrupted image
                try:
                    img = Image.open(item.path)
                except UnidentifiedImageError:
                    logger.debug(f"Skipped '{item.path}' as it's not an image.")
                    continue
                # Prefill with current dimensions so the list is never empty
                new_dimensions = (img.width, img.height)

                # Now recalculate the dimensions; start with width
                if img.width >= config["new_image"]["max_width"]:
                    new_dimensions = (
                        config["new_image"]["max_width"],
                        calulate_proprotional_change(
                            old_size=img.width,
                            new_size=config["new_image"]["max_width"],
                            second_dimension=img.height,
                        ),
                    )
                # Check the new height dimension in case max_height is still not reached
                if new_dimensions[1] >= config["new_image"]["max_height"]:
                    new_dimensions = (
                        calulate_proprotional_change(
                            old_size=new_dimensions[1],
                            new_size=config["new_image"]["max_height"],
                            second_dimension=new_dimensions[0],
                        ),
                        config["new_image"]["max_height"],
                    )

                new_path = f"{item.path.rsplit('.', 1)[0]}{config['new_image']['suffix']}.{item.path.rsplit('.', 1)[1]}"
                logger.debug(f"Resizing '{item.path}' to {new_dimensions}.")
                new_img = img.resize(size=new_dimensions)
                new_img.save(
                    new_path, "JPEG", quality=config["new_image"]["jpeg_quality"]
                )


if __name__ == "__main__":
    main()
