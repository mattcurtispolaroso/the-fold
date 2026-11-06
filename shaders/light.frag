#version 330 core

// Light accumulation (TA-3): ambient + sum of point/spot lights, one fullscreen pass.
// Pairs with upscale.vert. MAX_LIGHTS is rewritten from constants.LIGHT_SHADER_SLOTS
// at load time; arrays are padded and only the first u_light_count entries are read.
#define MAX_LIGHTS 11

uniform vec2 u_resolution;               // light buffer size in pixels
uniform vec3 u_ambient;
uniform int u_light_count;
uniform vec2 u_light_pos[MAX_LIGHTS];    // screen pixels, Y down
uniform vec3 u_light_color[MAX_LIGHTS];  // colour * intensity
uniform float u_light_radius[MAX_LIGHTS];
uniform vec2 u_light_dir[MAX_LIGHTS];    // unit vector, screen space (spot only)
uniform vec2 u_light_cone[MAX_LIGHTS];   // (cos outer, cos inner); point lights use (-2, -1)
uniform float u_max_brightness;

in vec2 v_screen_uv;
out vec4 f_color;

void main() {
    vec2 p = v_screen_uv * u_resolution;
    vec3 light = u_ambient;
    for (int i = 0; i < u_light_count; i++) {
        vec2 to_p = p - u_light_pos[i];
        float d = length(to_p);
        float falloff = clamp(1.0 - d / u_light_radius[i], 0.0, 1.0);
        falloff *= falloff;  // quadratic: soft centre, smooth edge
        float cone = 1.0;
        if (d > 0.0) {
            cone = smoothstep(u_light_cone[i].x, u_light_cone[i].y,
                              dot(to_p / d, u_light_dir[i]));
        }
        light += u_light_color[i] * falloff * cone;
    }
    f_color = vec4(min(light, vec3(u_max_brightness)), 1.0);
}
