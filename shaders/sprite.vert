#version 330 core

// Per-vertex: 2D screen-space position, atlas UV, RGBA tint
in vec2 a_pos;
in vec2 a_uv;
in vec4 a_tint;

// Screen size in pixels — used to convert to NDC
uniform vec2 u_resolution;

out vec2 v_uv;
out vec4 v_tint;

void main() {
    // Screen-space pixel coords (Y down) → NDC (Y up)
    vec2 ndc = a_pos / u_resolution * 2.0 - 1.0;
    gl_Position = vec4(ndc.x, -ndc.y, 0.0, 1.0);
    v_uv = a_uv;
    v_tint = a_tint;
}
