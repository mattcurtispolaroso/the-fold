#version 330 core

// Bloom step 1: keep only the bright parts of the scene (soft-knee threshold).
// Rendered into a downsampled buffer; linear filtering does the downsample.
uniform sampler2D u_texture;
uniform float u_threshold;
uniform float u_knee;

in vec2 v_uv;
out vec4 f_color;

void main() {
    vec3 color = texture(u_texture, v_uv).rgb;
    float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
    // Quadratic soft knee: 0 below threshold-knee, smooth ramp, linear above
    float soft = clamp(luma - u_threshold + u_knee, 0.0, 2.0 * u_knee);
    soft = soft * soft / (4.0 * u_knee + 1e-5);
    float weight = max(soft, luma - u_threshold) / max(luma, 1e-5);
    f_color = vec4(color * weight, 1.0);
}
