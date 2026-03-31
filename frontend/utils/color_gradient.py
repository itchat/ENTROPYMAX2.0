"""
Brown-to-yellow color gradient for group visualization.
"""


def brown_yellow_gradient(k: int) -> dict:
    """
    Generate a brown-to-yellow color gradient with k steps.

    Args:
        k: Number of groups

    Returns:
        Dictionary mapping group number (1-indexed) to hex color string.
        Group 1 = darkest brown (coarsest), Group k = lightest yellow (finest).
    """
    # SaddleBrown (139, 69, 19) -> Gold (255, 215, 0)
    start = (139, 69, 19)
    end = (255, 215, 0)

    if k == 1:
        return {1: '#{:02X}{:02X}{:02X}'.format(*start)}

    colors = {}
    for i in range(k):
        t = i / (k - 1)
        r = int(start[0] + t * (end[0] - start[0]))
        g = int(start[1] + t * (end[1] - start[1]))
        b = int(start[2] + t * (end[2] - start[2]))
        colors[i + 1] = '#{:02X}{:02X}{:02X}'.format(r, g, b)

    return colors
