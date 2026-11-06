#version 330 core

// Bloom step 3: add the blurred glow back onto the scene.
uniform sampler2D u_texture;  // scene
uniform sampler2D u_bloom;    // blurred bright pass (lower resolution)
uniform float u_intensity;

in vec2 v_uv;
out vec4 f_color;

void main() {
    vec3 scene = texture(u_texture, v_uv).rgb;
    vec3 glow = texture(u_bloom, v_uv).rgb;
    f_color = vec4(scene + glow * u_intensity, 1.0);
}
