#version 330 core

// Fold distortion (TA-5): expanding ripples, gravity-flip frame bend, and a
// chromatic aberration split. All distances are in framebuffer pixels (GL
// convention, origin bottom-left). Pixels are displaced by sampling from
// p - offset, so content moves along +offset.
// MAX_RIPPLES is rewritten from constants.DISTORTION_MAX_RIPPLES at load time.
#define MAX_RIPPLES 4

uniform sampler2D u_texture;
uniform vec2 u_resolution;
uniform int u_ripple_count;
uniform vec4 u_ripples[MAX_RIPPLES];  // centre x, centre y, ring radius, amplitude
uniform float u_ripple_width;
uniform vec3 u_bend;                  // direction x, y (unit, GL), amount
uniform float u_aberration;           // red/blue split at the corners
uniform float u_max_offset;           // hard cap on total displacement

in vec2 v_uv;
out vec4 f_color;

vec2 ripple_offset(vec2 p) {
    vec2 offset = vec2(0.0);
    for (int i = 0; i < u_ripple_count; i++) {
        vec2 d = p - u_ripples[i].xy;
        float dist = length(d);
        if (dist < 0.001) continue;
        float x = (dist - u_ripples[i].z) / u_ripple_width;
        offset += (d / dist) * exp(-x * x) * u_ripples[i].w;  // push outward on the ring
    }
    return offset;
}

vec2 bend_offset(vec2 uv) {
    // Bow along the gravity direction: full at the centre line, zero at the edges
    vec2 perp = vec2(-u_bend.y, u_bend.x);
    float t = dot(uv - 0.5, perp);  // -0.5..0.5 across the screen
    return u_bend.xy * u_bend.z * (1.0 - 4.0 * t * t);
}

void main() {
    vec2 p = v_uv * u_resolution;
    vec2 offset = ripple_offset(p) + bend_offset(v_uv);
    float len = length(offset);
    if (len > u_max_offset) offset *= u_max_offset / len;
    vec2 uv = (p - offset) / u_resolution;
    vec2 split = (v_uv - 0.5) * 2.0 * u_aberration / u_resolution;
    f_color = vec4(texture(u_texture, uv + split).r,
                   texture(u_texture, uv).g,
                   texture(u_texture, uv - split).b,
                   1.0);
}
