#version 330 core

// CRT / halation pass — STUB (TA Q5). The toggle is wired into PostStack and
// the debug overlay, but the look is deferred until the full post stack has
// been seen on real art. Currently an identity copy.
uniform sampler2D u_texture;

in vec2 v_uv;
out vec4 f_color;

void main() {
    f_color = vec4(texture(u_texture, v_uv).rgb, 1.0);
}
