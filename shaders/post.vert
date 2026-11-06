#version 330 core

// Fullscreen quad for post passes. v_uv is GL convention (origin bottom-left),
// matching how every FBO texture in the post stack is stored.
in vec2 a_pos;
out vec2 v_uv;

void main() {
    v_uv = a_pos * 0.5 + 0.5;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
