#version 330 core

// Soft round particle, premultiplied output (blend ONE, ONE_MINUS_SRC_ALPHA).
// Glow particles write alpha 0, which makes them purely additive — so normal
// and additive particles share one instanced draw call.
uniform float u_soft_edge;  // fraction of radius where normal particles start fading
uniform float u_glow_core;  // fraction of radius that glow particles keep at full brightness

in vec2 v_local;
in vec3 v_color;
in float v_alpha;
in float v_glow;

out vec4 f_color;

void main() {
    float d = length(v_local);
    if (d > 1.0) discard;
    float soft = 1.0 - smoothstep(u_soft_edge, 1.0, d);   // flat disc, soft rim (dust)
    float core = 1.0 - smoothstep(u_glow_core, 1.0, d);  // solid hot core, soft halo (glow)
    float shape = mix(soft, core, v_glow);
    float a = shape * v_alpha;
    f_color = vec4(v_color * a, a * (1.0 - v_glow));
}
