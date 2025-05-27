from PIL import Image
import numpy as np
import os

def get_color(v: float) -> tuple[int, int, int]:
    """
    Maps a numeric value to an RGB tuple based on rainfall intensity scale.
    """
    if 0 < v < 1:
        return (243, 243, 254)
    elif 1 <= v < 5:
        return (171, 213, 255)
    elif 5 <= v < 10:
        return (75, 151, 255)
    elif 10 <= v < 20:
        return (66, 91, 255)
    elif 20 <= v < 30:
        return (253, 249, 84)
    elif 30 <= v < 50:
        return (245, 164, 78)
    elif 50 <= v < 80:
        return (240, 77, 73)
    else:
        return (183, 54, 127)

def ascii2img(data: np.ndarray, png_path: str, alpha: int = 200) -> None:
    """
    Converts a 2D NumPy array to an RGBA PNG image.

    Parameters:
        data (np.ndarray): 2D array of numeric values.
        png_path (str): Output file path for the PNG image.
        alpha (int): Alpha value for non-zero cells (0-255).
    """
    if data.ndim != 2:
        raise ValueError("Input data must be a 2D array.")

    rows, cols = data.shape
    img = Image.new("RGBA", (cols, rows), (0, 0, 0, 0))
    pixels = img.load()

    for y in range(rows):
        for x in range(cols):
            val = data[y, x]
            if val <= 0:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                r, g, b = get_color(val)
                pixels[x, y] = (r, g, b, alpha)

    try:
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        img.save(png_path, "PNG")
    except Exception as e:
        raise IOError(f"Failed to save PNG image to {png_path}: {e}")
