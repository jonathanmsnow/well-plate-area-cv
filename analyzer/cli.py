from analyzer.image_processor import ImageProcessor
from analyzer.well_detector import WellDetector
from analyzer.well_analyzer import WellAnalyzer
from analyzer.visualizer import Visualizer
from analyzer.hsv_thresholder import HsvThresolder
from analyzer.config_manager import ConfigManager
from pathlib import Path
import os
import click


@click.group()
def cli():
    pass

@cli.command()
@click.option(
    "-i",
    "--image",
    "image",
    type=click.Path(path_type=Path, dir_okay=False),
    multiple=False,
    help="The image file to open.",
)
@click.option(
    "-w",
    "--width",
    "width",
    type=click.INT,
    help="The desired width to display the image.",
)
@click.option(
    "-c",
    "--config",
    "config",
    type=click.Path(path_type=Path),
    help="The config to be updated with the chosen HSV range.",
)
def threshold(image, width, config):
    """Helper to determine optimal threshold values for masking items of interest"""
    thresholder = HsvThresolder(image)
    lower_bound, upper_bound = thresholder.threshold(width)
    new_min_max_threshold = {
        "well_analyzer": {
            "hsv_lower_bound": lower_bound,
            "hsv_upper_bound": upper_bound
        }
    }
    config_manager = ConfigManager(config)
    config_manager.update(new_min_max_threshold)
    config_manager.write()

@cli.command()
@click.option(
    "-i",
    "--image",
    "images",
    type=click.Path(path_type=Path),
    multiple=False,
    help="The image file to open.",
)
@click.option('--dp', default=1, help='Inverse ratio of the accumulator resolution to the image resolution.')
@click.option('--min_dist', default=270, help='Minimum distance between the centers of detected circles.')
@click.option('--param1', default=45, help='First method-specific parameter for the edge detection.')
@click.option('--param2', default=20, help='Second method-specific parameter for the center detection.')
@click.option('--min_radius', default=120, help='Minimum circle radius to detect.')
@click.option('--max_radius', default=145, help='Maximum circle radius to detect.')
@click.option(
    "-c",
    "--config",
    "config",
    type=click.Path(path_type=Path),
    help="The config to use. Cannot be combined with individual params for configuration.",
)
@click.option(
    "-o",
    "--output",
    "output",
    type=click.Path(path_type=Path, dir_okay=True),
    multiple=False,
    help="The name of the directory to output to.",
)
def process(images, config, output, dp, min_dist, param1, param2, min_radius, max_radius):
    """Processes images"""

    if config:
        try:
            config_manager = ConfigManager(config)
            config_data = config_manager.load()
            dp = dp or config_data.get('dp', 1)
            min_dist = min_dist or config_data.get('min_dist', 270)
            param1 = param1 or config_data.get('param1', 45)
            param2 = param2 or config_data.get('param2', 20)
            min_radius = min_radius or config_data.get('min_radius', 120)
            max_radius = max_radius or config_data.get('max_radius', 145)
        except:
            click.echo(f"Failed while process config file {config}")
    else:
        # If no config file, use CLI values with defaults
        dp = dp or 1
        min_dist = min_dist or 270
        param1 = param1 or 45
        param2 = param2 or 20
        min_adius = min_adius or 120
        max_radius = max_radius or 145

    def process_image(image_path, output):
        click.echo(f'Processing {image_path}')
        # Step 1: Load and preprocess the image
        processor = ImageProcessor(image_path)
        blurred_image = processor.get_blurred_image()

        # Step 2: Detect and sort circles (wells)
        detector = WellDetector(blurred_image)
        detected_circles = detector.detect_wells(dp, min_dist, param1, param2, min_radius, max_radius)
        sorted_circles = detector.sort_circles(detected_circles)

        # Step 3: Analyze duckweed for each well
        analyzer = WellAnalyzer(processor.get_original_image())
        visualizer = Visualizer(processor.get_original_image(), sorted_circles)

        csv_out = []
        csv_out.append("Well,area")
        for i, (x, y, r) in enumerate(sorted_circles):
            # Analyze the duckweed in the current well
            contours, total_area = analyzer.analyze_plant_area(x, y, r)

            # Draw the circle and contours on the image
            visualizer.draw_contours(contours)
            visualizer.add_text(x, y, r, f"Well {i}: {total_area} px")

            # add well number and area to output
            csv_out.append(f"{i},{total_area}")

        # Step 4: Display the final annotated image
        visualizer.draw_circles()
        #visualizer.show_image('Identified Wells', 1440)

        os.makedirs(output, exist_ok=True)
        out_name = os.path.splitext(os.path.basename(image_path))[0]
        out_file = str(output) + "/" + out_name + ".csv"
        with open(out_file, 'w') as f:
            for line in csv_out:
                f.write(line + '\n')

        out_image = str(output) + "/" + out_name + "_annotated.png"
        visualizer.save_image(out_image)


    if images.is_dir():
        for image_path in images.iterdir():
            process_image(image_path, output)
    else:
        process_image(images, output)


@cli.command()
@click.option(
    "-f",
    "--file",
    "file",
    type=click.Path(path_type=Path),
    help="The config file path.",
)
def config(file):
    """Generates a new config file"""
    if file:
        config_manager = ConfigManager(file)
        config_manager.generate()
    else:
        config_manager = ConfigManager()
        config_manager.generate()

# # Run the program
if __name__ == "__main__":
    cli()
