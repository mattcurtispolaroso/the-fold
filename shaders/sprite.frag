#version 330 core

uniform sampler2D u_texture;

in vec2 v_uv;
in vec4 v_tint;

out vec4 f_color;

void main() {
    f_color = texture(u_texture, v_uv) * v_tint;
}
