#version 330 core

// Bloom step 2: one direction of a separable 9-tap Gaussian blur.
// u_direction is one texel along x (horizontal) or y (vertical).
uniform sampler2D u_texture;
uniform vec2 u_direction;

in vec2 v_uv;
out vec4 f_color;

const float WEIGHTS[5] = float[](0.2270270, 0.1945946, 0.1216216, 0.0540541, 0.0162162);

void main() {
    vec3 sum = texture(u_texture, v_uv).rgb * WEIGHTS[0];
    for (int i = 1; i < 5; i++) {
        vec2 offset = u_direction * float(i);
        sum += texture(u_texture, v_uv + offset).rgb * WEIGHTS[i];
        sum += texture(u_texture, v_uv - offset).rgb * WEIGHTS[i];
    }
    f_color = vec4(sum, 1.0);
}
