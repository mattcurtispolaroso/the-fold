#version 330 core

// Final post-stack blit: copy the processed frame to the target framebuffer.
// The viewport sets the output size, so this is also the display upscale.
uniform sampler2D u_texture;

in vec2 v_uv;
out vec4 f_color;

void main() {
    f_color = vec4(texture(u_texture, v_uv).rgb, 1.0);
}
