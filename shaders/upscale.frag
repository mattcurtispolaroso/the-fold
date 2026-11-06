#version 330 core

// Samples a texture across the viewport with an optional scroll offset.
// Mirror-wrapping lets a single screen-sized image scroll without seams.
// With u_uv_offset = 0 this is an identity copy (layer composite / upscale).
uniform sampler2D u_texture;
uniform vec2 u_uv_offset;   // in screen-UV units (pixels / layer size), Y down

in vec2 v_screen_uv;
out vec4 f_color;

vec2 mirror_wrap(vec2 uv) {
    return 1.0 - abs(mod(uv, 2.0) - 1.0);
}

void main() {
    vec2 uv = mirror_wrap(v_screen_uv + u_uv_offset);
    // Textures are uploaded flipped (GL V = 1 at the top of the image)
    f_color = texture(u_texture, vec2(uv.x, 1.0 - uv.y));
}
