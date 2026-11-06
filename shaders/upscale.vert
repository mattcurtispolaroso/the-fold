#version 330 core

// Fullscreen quad in NDC. The viewport decides the output size, so the same
// shader draws layer images into 800x600 FBOs and upscales them to the window.
in vec2 a_pos;

// Screen-space UV, origin top-left, Y down (matches pygame / world coords)
out vec2 v_screen_uv;

void main() {
    v_screen_uv = vec2(a_pos.x * 0.5 + 0.5, 0.5 - a_pos.y * 0.5);
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
