#version 330 core

// Film grain: per-pixel hash noise, reseeded every frame via u_seed.
// Scaled down in shadows so near-black art is not swamped by noise.
uniform sampler2D u_texture;
uniform vec2 u_resolution;
uniform float u_seed;
uniform float u_amount;
uniform float u_shadow_scale;  // grain multiplier at black
uniform float u_full_luma;     // luminance where grain reaches full amplitude

in vec2 v_uv;
out vec4 f_color;

float hash(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void main() {
    vec2 pixel = floor(v_uv * u_resolution);
    float noise = hash(pixel + vec2(u_seed * 17.0, u_seed * 31.0)) * 2.0 - 1.0;
    vec3 color = texture(u_texture, v_uv).rgb;
    float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
    float amplitude = u_amount * mix(u_shadow_scale, 1.0, smoothstep(0.0, u_full_luma, luma));
    f_color = vec4(color + noise * amplitude, 1.0);
}
