#version 330 core

// Tinted sprite with an optional flash (TA-6): rgb is mixed toward the flash
// colour by flash.a. Alpha is untouched, so the flash is a silhouette.
uniform sampler2D u_texture;

in vec2 v_uv;
in vec4 v_tint;
in vec4 v_flash;

out vec4 f_color;

void main() {
    vec4 color = texture(u_texture, v_uv) * v_tint;
    color.rgb = mix(color.rgb, v_flash.rgb, v_flash.a);
    f_color = color;
}
