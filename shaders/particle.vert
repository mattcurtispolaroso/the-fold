#version 330 core

// Instanced particle quad (TA-7). One unit quad, one instance per particle.
in vec2 a_corner;    // per-vertex: -1..1
in vec2 i_pos;       // per-instance: screen pixels, Y down
in float i_radius;   // px
in vec3 i_color;
in float i_alpha;    // remaining life fraction
in float i_glow;     // 1 = additive/emissive, 0 = normal

uniform vec2 u_resolution;

out vec2 v_local;
out vec3 v_color;
out float v_alpha;
out float v_glow;

void main() {
    vec2 pos = i_pos + a_corner * i_radius;
    vec2 ndc = pos / u_resolution * 2.0 - 1.0;
    gl_Position = vec4(ndc.x, -ndc.y, 0.0, 1.0);
    v_local = a_corner;
    v_color = i_color;
    v_alpha = i_alpha;
    v_glow = i_glow;
}
