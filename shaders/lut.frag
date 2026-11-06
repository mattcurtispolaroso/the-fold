#version 330 core

// Colour grade through a 3D lookup table. Input is clamped to [0,1] first,
// so this is also where HDR from the light buffer is brought back into range.
uniform sampler2D u_texture;
uniform sampler3D u_lut;
uniform float u_lut_size;
uniform float u_strength;

in vec2 v_uv;
out vec4 f_color;

void main() {
    vec3 color = clamp(texture(u_texture, v_uv).rgb, 0.0, 1.0);
    // Sample texel centres: map [0,1] onto [0.5/N, 1 - 0.5/N]
    vec3 coord = color * ((u_lut_size - 1.0) / u_lut_size) + 0.5 / u_lut_size;
    vec3 graded = texture(u_lut, coord).rgb;
    f_color = vec4(mix(color, graded, u_strength), 1.0);
}
