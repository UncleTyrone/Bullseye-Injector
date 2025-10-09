#!/usr/bin/env python3

"""Sprite replacement pipeline.

For each sprite in `TakeMoveTypeFrom`, detects the main Pokémon sprite bounding box
and replaces it with the corresponding image from `TakeSpriteFrom` while keeping the
badges intact. Outputs processed sprites and logs with bounding boxes.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from PIL import Image, ImageSequence

BoundingBox = Tuple[int, int, int, int]  # (left, top, right, bottom) with right/bottom exclusive





@dataclass
class Component:
    bbox: BoundingBox
    pixel_count: int





def configure_logging(log_dir: Path) -> logging.Logger:

    """Configure a logger that writes to file and stdout."""

    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("sprite_processor")

    logger.setLevel(logging.INFO)

    # Clear any default handlers to avoid duplicated logs when re-running.

    logger.handlers.clear()



    log_path = log_dir / "process.log"

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")

    console_handler = logging.StreamHandler()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler.setFormatter(formatter)

    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    logger.addHandler(console_handler)

    return logger





def load_rgba_image(path: Path) -> Image.Image:

    """Load an image and ensure it is in RGBA mode."""

    with Image.open(path) as img:

        return img.convert("RGBA")





def load_animated_rgba_frames(path: Path) -> Tuple[List[Image.Image], List[int], int, List[int]]:
    """Load all frames from an image as RGBA along with timing metadata."""
    with Image.open(path) as img:
        loop = (img.info.get("loop", 0) or 0)
        default_duration = img.info.get("duration", 100) or 100
        default_disposal = img.info.get("disposal", 2)

        frames: List[Image.Image] = []
        durations: List[int] = []
        disposals: List[int] = []

        for frame in ImageSequence.Iterator(img):
            duration = frame.info.get("duration", default_duration) or default_duration
            durations.append(duration)
            disposals.append(frame.info.get("disposal", default_disposal))
            frames.append(frame.convert("RGBA"))

        if not frames:
            frames.append(img.convert("RGBA"))
            durations.append(default_duration)
            disposals.append(default_disposal)

    return frames, durations, loop, disposals



def union_frame_bbox(frames: Iterable[Image.Image]) -> Optional[BoundingBox]:
    """Return the union bounding box of non-transparent pixels across frames."""
    boxes = [frame.getbbox() for frame in frames if frame.getbbox()]
    if not boxes:
        return None

    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    return left, top, right, bottom



def resize_animation_frames(frames: List[Image.Image], size: Tuple[int, int]) -> List[Image.Image]:
    """Resize an animated sequence to the target size while keeping alignment."""
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError(f"Invalid resize dimensions: {size}")

    content_bbox = union_frame_bbox(frames)
    resized_frames: List[Image.Image] = []
    for frame in frames:
        working = frame
        if content_bbox:
            working = frame.crop(content_bbox)
        # Use smart resampling: NEAREST for integer scaling, LANCZOS for non-integer
        scale_x = size[0] / working.width
        scale_y = size[1] / working.height
        if scale_x == int(scale_x) and scale_y == int(scale_y) and scale_x >= 1.0 and scale_y >= 1.0:
            # Integer upscaling - use NEAREST for crisp pixel art
            resized_frames.append(working.resize(size, Image.Resampling.NEAREST))
        else:
            # Non-integer scaling - use LANCZOS for smoother results
            resized_frames.append(working.resize(size, Image.Resampling.LANCZOS))
    return resized_frames


def resize_animation_frames_preserve_aspect(frames: List[Image.Image], max_size: Tuple[int, int]) -> List[Image.Image]:
    """Resize an animated sequence to fit well within max_size while preserving aspect ratio."""
    if max_size[0] <= 0 or max_size[1] <= 0:
        raise ValueError(f"Invalid max dimensions: {max_size}")

    # Get the union bounding box across ALL frames to account for animation movement
    content_bbox = union_frame_bbox(frames)
    if not content_bbox:
        return frames
    
    # Calculate the scale required to fit within the requested max size
    max_width, max_height = max_size
    bbox_width = content_bbox[2] - content_bbox[0]
    bbox_height = content_bbox[3] - content_bbox[1]
    scale_limit = min(max_width / bbox_width, max_height / bbox_height)
    scale = min(1.0, scale_limit)

    resized_frames: List[Image.Image] = []
    for frame in frames:
        working = frame.crop(content_bbox)

        if scale < 1.0:
            new_width = max(1, int(round(working.size[0] * scale)))
            new_height = max(1, int(round(working.size[1] * scale)))
            resized_frames.append(working.resize((new_width, new_height), Image.Resampling.LANCZOS))
        else:
            resized_frames.append(working.copy())
    return resized_frames



def normalize_durations(durations: List[int], frame_count: int, fallback: int = 100) -> List[int]:
    """Ensure the duration list matches the number of frames."""
    if frame_count <= 0:
        return []

    if not durations:
        durations = [fallback] * frame_count
    else:
        durations = [duration or fallback for duration in durations]

    if len(durations) < frame_count:
        durations.extend([durations[-1]] * (frame_count - len(durations)))
    elif len(durations) > frame_count:
        durations = durations[:frame_count]

    return durations



def extract_components(alpha: Image.Image) -> List[Component]:

    """Return connected components for the alpha channel using 4-neighbourhood."""

    w, h = alpha.size

    pixels = alpha.load()

    visited = [[False] * w for _ in range(h)]

    components: List[Component] = []



    for y in range(h):

        for x in range(w):

            if visited[y][x]:

                continue

            visited[y][x] = True

            # Use a higher threshold to filter out very low alpha values (likely artifacts)
            if pixels[x, y] < 32:  # Only consider pixels with alpha >= 32 (out of 255)

                continue



            stack = [(x, y)]

            min_x = max_x = x

            min_y = max_y = y

            count = 0



            while stack:

                cx, cy = stack.pop()

                count += 1

                if cx < min_x:

                    min_x = cx

                if cx > max_x:

                    max_x = cx

                if cy < min_y:

                    min_y = cy

                if cy > max_y:

                    max_y = cy



                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):

                    if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:

                        visited[ny][nx] = True

                        # Use the same threshold for connected components
                        if pixels[nx, ny] >= 32:

                            stack.append((nx, ny))



            bbox: BoundingBox = (min_x, min_y, max_x + 1, max_y + 1)

            components.append(Component(bbox=bbox, pixel_count=count))



    components.sort(key=lambda comp: comp.pixel_count, reverse=True)

    return components





def classify_components(components: Iterable[Component], min_pixel_threshold: int = 100) -> Tuple[Optional[Component], List[Component]]:

    """Return the largest component as the main sprite; only small, corner-positioned components as badges.

    Filters out very small components and large secondary components (like cloud effects) that should not be preserved.

    Args:

        components: List of detected components

        min_pixel_threshold: Minimum pixel count for a component to be considered valid

    """

    comps = list(components)

    if not comps:

        return None, []

    # Filter out very small components (likely runaway pixels)

    valid_comps = [comp for comp in comps if comp.pixel_count >= min_pixel_threshold]

    if not valid_comps:

        # If no components meet the threshold, fall back to the largest one

        valid_comps = [comps[0]]

    main = valid_comps[0]
    
    # Be selective about what counts as a "badge" - exclude large background effects but keep real badges
    # Only consider components that are:
    # 1. Smaller than the main sprite (less than 40% of main sprite size)
    # 2. Not excessively large in absolute terms (less than 2000 pixels)
    # 3. Not heavily overlapping with main sprite (likely part of Pokemon)
    
    potential_badges = valid_comps[1:]  # All components except the main one
    badges = []
    
    for comp in potential_badges:
        # Size check: must be smaller than main sprite, but not too restrictive
        size_ratio = comp.pixel_count / main.pixel_count
        if size_ratio > 0.40:  # Skip components larger than 40% of main sprite (was 15%)
            continue
            
        # Absolute size check: filter out very large background effects
        if comp.pixel_count > 2000:  # Skip very large components (was 800)
            continue
            
        # Position check: skip components that heavily overlap with main sprite
        comp_left, comp_top, comp_right, comp_bottom = comp.bbox
        main_left, main_top, main_right, main_bottom = main.bbox
        
        # Check if component overlaps significantly with main sprite (likely part of the Pokemon)
        overlap_x = max(0, min(comp_right, main_right) - max(comp_left, main_left))
        overlap_y = max(0, min(comp_bottom, main_bottom) - max(comp_top, main_top))
        overlap_area = overlap_x * overlap_y
        comp_area = (comp_right - comp_left) * (comp_bottom - comp_top)
        
        if overlap_area > comp_area * 0.5:  # Skip if more than 50% overlap with main sprite (was 30%)
            continue
            
        # If it passes all checks, it's likely a real badge
        badges.append(comp)

    badges.sort(key=lambda comp: comp.bbox[1])

    return main, badges





def crop_to_content(image: Image.Image) -> Image.Image:

    """Crop the image to the bounding box of non-transparent pixels."""

    alpha = image.split()[3]

    bbox = alpha.getbbox()

    if bbox is None:

        return image

    return image.crop(bbox)


def clean_edge_pixels(image: Image.Image, bbox: BoundingBox, cleanup_radius: int = 2) -> Image.Image:

    """Clean up edge pixels around a bounding box to remove stray pixels."""

    result = image.copy()

    left, top, right, bottom = bbox

    

    # Expand the cleanup area slightly beyond the bounding box

    cleanup_left = max(0, left - cleanup_radius)

    cleanup_top = max(0, top - cleanup_radius)

    cleanup_right = min(image.width, right + cleanup_radius)

    cleanup_bottom = min(image.height, bottom + cleanup_radius)

    

    # Create a mask for the cleanup area

    mask = Image.new('L', image.size, 0)

    cleanup_mask = Image.new('L', (cleanup_right - cleanup_left, cleanup_bottom - cleanup_top), 255)

    mask.paste(cleanup_mask, (cleanup_left, cleanup_top))

    

    # Clear the cleanup area

    transparent = Image.new('RGBA', (cleanup_right - cleanup_left, cleanup_bottom - cleanup_top), (0, 0, 0, 0))

    result.paste(transparent, (cleanup_left, cleanup_top), cleanup_mask)

    

    return result


def aggressive_background_cleanup(image: Image.Image, preserve_components: List[Component]) -> Image.Image:

    """Aggressively clean the background, only preserving specified components."""

    result = Image.new('RGBA', image.size, (0, 0, 0, 0))

    

    # Only preserve the specified components

    for component in preserve_components:

        component_img = image.crop(component.bbox)

        result.paste(component_img, (component.bbox[0], component.bbox[1]), component_img)

    

    return result





def resize_sprite(sprite: Image.Image, size: Tuple[int, int]) -> Image.Image:

    """Resize sprite to target size using high-quality resampling."""

    if size[0] <= 0 or size[1] <= 0:

        raise ValueError(f"Invalid resize dimensions: {size}")

    cropped = crop_to_content(sprite)

    # Use smart resampling: NEAREST for integer scaling, LANCZOS for non-integer
    scale_x = size[0] / cropped.width
    scale_y = size[1] / cropped.height
    if scale_x == int(scale_x) and scale_y == int(scale_y) and scale_x >= 1.0 and scale_y >= 1.0:
        # Integer upscaling - use NEAREST for crisp pixel art
        return cropped.resize(size, Image.Resampling.NEAREST)
    else:
        # Non-integer scaling - use LANCZOS for smoother results
        return cropped.resize(size, Image.Resampling.LANCZOS)





def paste_sprite(base: Image.Image, sprite: Image.Image, bbox: BoundingBox) -> Image.Image:

    """Paste the sprite into the base image at the provided bounding box."""

    left, top, right, bottom = bbox

    width = right - left

    height = bottom - top

    if sprite.size != (width, height):

        # Use smart resampling: NEAREST for integer scaling, LANCZOS for non-integer
        scale_x = width / sprite.width
        scale_y = height / sprite.height
        if scale_x == int(scale_x) and scale_y == int(scale_y) and scale_x >= 1.0 and scale_y >= 1.0:
            # Integer upscaling - use NEAREST for crisp pixel art
            sprite = sprite.resize((width, height), Image.Resampling.NEAREST)
        else:
            # Non-integer scaling - use LANCZOS for smoother results
            sprite = sprite.resize((width, height), Image.Resampling.LANCZOS)

    result = base.copy()

    result.paste(sprite, (left, top), sprite)

    return result





def process_pair(move_img_path: Path, sprite_path: Path, output_dir: Path, logger: logging.Logger) -> Optional[dict]:
    """Process a single pair of sprites."""
    base_frames, _, _, _ = load_animated_rgba_frames(move_img_path)
    if not base_frames:
        logger.warning("%s: unable to read base sprite frames", move_img_path.name)
        return None

    base_frame = base_frames[0]
    components = extract_components(base_frame.split()[3])
    main_component, badge_components = classify_components(components)

    if main_component is None:
        logger.warning("%s: no opaque components detected", move_img_path.name)
        return None

    bbox = main_component.bbox
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    if width <= 0 or height <= 0:
        logger.warning("%s: invalid bounding box %s", move_img_path.name, bbox)
        return None

    if not sprite_path.exists():
        logger.warning("%s: corresponding sprite missing at %s", move_img_path.name, sprite_path)
        return None

    replacement_frames, durations, loop, _ = load_animated_rgba_frames(sprite_path)
    
    # Get the union bounding box of the replacement sprite to understand its full animation range
    replacement_bbox = union_frame_bbox(replacement_frames)
    if not replacement_bbox:
        logger.warning("%s: replacement sprite has no content", move_img_path.name)
        return None
    
    # Calculate the actual content dimensions of the replacement sprite
    replacement_width = replacement_bbox[2] - replacement_bbox[0]
    replacement_height = replacement_bbox[3] - replacement_bbox[1]
    
    # NEW APPROACH: Calculate proportion between bullseye sprite bbox and total canvas
    # This preserves quality by avoiding downsampling of larger replacement sprites
    bullseye_bbox_width = bbox[2] - bbox[0]
    bullseye_bbox_height = bbox[3] - bbox[1]
    
    # Calculate the proportion of the bullseye sprite bbox to the total canvas
    bbox_to_canvas_ratio_x = bullseye_bbox_width / base_frame.width
    bbox_to_canvas_ratio_y = bullseye_bbox_height / base_frame.height
    
    # Determine if we need to scale up the canvas to accommodate larger replacement sprites
    scale_factor = 1.0
    if replacement_width > bullseye_bbox_width or replacement_height > bullseye_bbox_height:
        # Calculate scale factor needed to fit the replacement sprite
        scale_x = replacement_width / bullseye_bbox_width
        scale_y = replacement_height / bullseye_bbox_height
        scale_factor = max(scale_x, scale_y)
        
        logger.info("%s: replacement sprite larger than bullseye (%.2fx), scaling canvas by %.2fx", 
                   move_img_path.name, scale_factor, scale_factor)
    
    # Calculate new canvas dimensions based on scale factor
    new_canvas_width = int(base_frame.width * scale_factor)
    new_canvas_height = int(base_frame.height * scale_factor)
    
    # Calculate new bbox position and size in the scaled canvas
    new_bbox_left = int(bbox[0] * scale_factor)
    new_bbox_top = int(bbox[1] * scale_factor)
    new_bbox_right = int(bbox[2] * scale_factor)
    new_bbox_bottom = int(bbox[3] * scale_factor)
    new_bbox_width = new_bbox_right - new_bbox_left
    new_bbox_height = new_bbox_bottom - new_bbox_top
    
    # Crop replacement frames to their content bbox (no scaling - preserve quality)
    cropped_replacement_frames = []
    for frame in replacement_frames:
        cropped_frame = frame.crop(replacement_bbox)
        cropped_replacement_frames.append(cropped_frame)
    
    # Calculate gap for type indicators
    desired_gap = 8
    badge_left = min((component.bbox[0] for component in badge_components), default=base_frame.width)
    current_gap = badge_left - bbox[2]
    required_shift = max(0, desired_gap - current_gap)
    
    # Scale the required shift for the new canvas
    scaled_required_shift = int(required_shift * scale_factor)
    
    # Final canvas dimensions including space for type indicators
    canvas_width = new_canvas_width + scaled_required_shift
    canvas_height = new_canvas_height

    # Create a completely clean base - no badges yet, they'll be added in the composition loop
    base_clean = Image.new('RGBA', (new_canvas_width, new_canvas_height), (0, 0, 0, 0))

    # Prepare badge layers for the final composition
    # Type indicators stay at their original size and are positioned relative to the scaled canvas
    badge_layers = []
    shifted_badge_bboxes: List[List[int]] = []
    for component in badge_components:
        badge_img = base_frame.crop(component.bbox)
        
        # Keep type indicators at their original size but position them relative to the scaled canvas
        # Type indicators should not be scaled up - they should maintain their original size
        original_badge_left = component.bbox[0]
        original_badge_top = component.bbox[1]
        original_badge_right = component.bbox[2]
        original_badge_bottom = component.bbox[3]
        
        # Scale the horizontal position to match the scaled canvas
        scaled_badge_left = int(original_badge_left * scale_factor)
        
        # Anchor type indicators to the bottom right of the canvas
        # Position from bottom of canvas to maintain proper stacking
        badge_height = original_badge_bottom - original_badge_top
        original_badge_top = component.bbox[1]
        
        # Calculate position from bottom of canvas (bottom-right anchor)
        final_badge_left = scaled_badge_left + scaled_required_shift
        # Position from bottom: canvas_height - distance_from_bottom
        distance_from_bottom = base_frame.height - original_badge_bottom
        final_badge_top = canvas_height - distance_from_bottom - badge_height
        
        badge_layers.append((badge_img, final_badge_left, final_badge_top))
        shifted_badge_bboxes.append([
            final_badge_left,
            final_badge_top,
            final_badge_left + (original_badge_right - original_badge_left),
            final_badge_top + (original_badge_bottom - original_badge_top),
        ])

    base_canvas = Image.new("RGBA", (canvas_width, canvas_height))
    base_canvas.paste(base_clean, (0, 0))

    output_frames: List[Image.Image] = []
    for i, cropped_frame in enumerate(cropped_replacement_frames):
        canvas = base_canvas.copy()
        
        # Position the cropped replacement frame in the scaled canvas
        # Center horizontally around the scaled bbox center, align to bottom vertically
        frame_width, frame_height = cropped_frame.size
        
        # Center horizontally around the scaled bbox center
        scaled_bbox_center_x = new_bbox_left + new_bbox_width // 2
        paste_x = scaled_bbox_center_x - frame_width // 2
        
        # Align to the bottom of the scaled bounding box for consistency
        paste_y = new_bbox_bottom - frame_height
        
        # Ensure we don't go outside the canvas bounds
        paste_x = max(0, min(paste_x, canvas_width - frame_width))
        paste_y = max(0, min(paste_y, canvas_height - frame_height))
        
        # Use the cropped frame as both image and mask for cleaner pasting
        canvas.paste(cropped_frame, (paste_x, paste_y), cropped_frame)
        
        # Add type indicators at their scaled positions
        for badge_img, badge_left, badge_top in badge_layers:
            canvas.paste(badge_img, (badge_left, badge_top), badge_img)
        
        output_frames.append(canvas)

    durations = normalize_durations(durations, len(output_frames))
    loop = loop or 0

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / move_img_path.name

    output_frames[0].save(
        output_path,
        save_all=True,
        append_images=output_frames[1:],
        loop=loop,
        duration=durations,
        disposal=2,
    )

    logger.info(
        "%s: composited animated sprite (scale=%.2fx, bbox=%s, shift=%s) using %s -> %s",
        move_img_path.name,
        scale_factor,
        bbox,
        scaled_required_shift,
        sprite_path.name,
        output_path,
    )

    return {
        "main_bbox": list(bbox),
        "badge_bboxes": shifted_badge_bboxes,
        "output_path": str(output_path),
        "badge_shift": scaled_required_shift,
        "scale_factor": scale_factor,
        "canvas_size": (canvas_width, canvas_height),
    }



def run_pipeline(move_dir: Path, sprite_dir: Path, output_dir: Path, log_dir: Path, limit: Optional[int] = None) -> None:

    logger = configure_logging(log_dir)

    logger.info("Starting sprite processing")



    results = {}

    move_paths = sorted(p for p in move_dir.iterdir() if p.is_file())

    if limit is not None:

        move_paths = move_paths[:limit]



    for move_path in move_paths:

        sprite_path = sprite_dir / move_path.name

        try:

            result = process_pair(move_path, sprite_path, output_dir, logger)

            if result:

                results[move_path.name] = result

        except Exception as exc:  # pylint: disable=broad-except

            logger.exception("%s: failed to process pair due to %s", move_path.name, exc)



    summary_path = log_dir / "bounding_boxes.json"

    with summary_path.open("w", encoding="utf-8") as fh:

        json.dump(results, fh, indent=2)

    logger.info("Wrote bounding box summary to %s", summary_path)

    logger.info("Completed sprite processing (%d successful)", len(results))





def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:

    parser = argparse.ArgumentParser(description="Replace Pokémon sprites while keeping badges.")

    parser.add_argument("--move-dir", type=Path, default=Path("TakeMoveTypeFrom"), help="Directory containing original sprites with badges")

    parser.add_argument("--sprite-dir", type=Path, default=Path("TakeSpriteFrom"), help="Directory containing replacement sprites")

    parser.add_argument("--output-dir", type=Path, default=Path("ProcessedSprites"), help="Directory to write composited sprites")

    parser.add_argument("--log-dir", type=Path, default=Path("logs"), help="Directory to write logs and summaries")

    parser.add_argument("--limit", type=int, default=None, help="Optionally limit number of sprites processed")

    return parser.parse_args(argv)





def main() -> None:

    args = parse_args()

    run_pipeline(args.move_dir, args.sprite_dir, args.output_dir, args.log_dir, args.limit)





if __name__ == "__main__":

    main()







