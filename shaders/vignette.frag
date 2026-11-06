#version 330 core

// Radial darkening toward the screen edges. Distance is aspect-corrected and
// normalised so 1.0 is the corner. Mirrors post_stack.vignette_factor().
uniform sampler2D u_texture;
uniform vec2 u_resolution;
uniform float u_strength;
uniform float u_inner;
uniform float u_outer;

in vec2 v_uv;
out vec4 f_color;

void main() {
    vec2 centred = (v_uv - 0.5) * u_resolution;
    float dist = length(centred) / length(0.5 * u_resolution);
    float factor = 1.0 - u_strength * smoothstep(u_inner, u_outer, dist);
    f_color = vec4(texture(u_texture, v_uv).rgb * factor, 1.0);
}
