def world_to_screen(matrix, pos_x, pos_y, pos_z, window_width=1920, window_height=1080):
    # 1. Multiply 3D world coordinates by the 4x4 ViewMatrix
    # Matrix layout is typically a flat list or array of 16 floats
    transformed_x = matrix[0] * pos_x + matrix[1] * pos_y + matrix[2] * pos_z + matrix[3]
    transformed_y = matrix[4] * pos_x + matrix[5] * pos_y + matrix[6] * pos_z + matrix[7]
    w = matrix[12] * pos_x + matrix[13] * pos_y + matrix[14] * pos_z + matrix[15]

    # 2. Check if the target is behind the camera
    if w < 0.01:
        return None  # Out of bounds / behind screen

    # 3. Perspective divide to get Normalized Device Coordinates (NDC)
    inv_w = 1.0 / w
    ndc_x = transformed_x * inv_w
    ndc_y = transformed_y * inv_w

    # 4. Convert NDC into actual screen pixel coordinates
    x = (window_width / 2.0) + (0.5 * ndc_x * window_width + 0.5)
    y = (window_height / 2.0) - (0.5 * ndc_y * window_height + 0.5)

    return (int(x), int(y))
