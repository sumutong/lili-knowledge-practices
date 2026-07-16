//! Rust WASM 实战
//! WebAssembly 计算器 & 图像滤镜，编译后在浏览器中运行

use wasm_bindgen::prelude::*;

/// 计算器：四则运算
#[wasm_bindgen]
pub fn calculate(a: f64, b: f64, op: &str) -> f64 {
    match op {
        "+" => a + b,
        "-" => a - b,
        "*" => a * b,
        "/" => {
            if b == 0.0 {
                f64::NAN
            } else {
                a / b
            }
        }
        _ => f64::NAN,
    }
}

/// 斐波那契数列
#[wasm_bindgen]
pub fn fibonacci(n: u32) -> u64 {
    if n <= 1 {
        return n as u64;
    }
    let mut a = 0u64;
    let mut b = 1u64;
    for _ in 2..=n {
        let temp = a.wrapping_add(b);
        a = b;
        b = temp;
    }
    b
}

/// 灰度转换：将 RGBA 像素数组转为灰度
#[wasm_bindgen]
pub fn grayscale(pixels: &mut [u8]) {
    for chunk in pixels.chunks_mut(4) {
        let r = chunk[0] as f64;
        let g = chunk[1] as f64;
        let b_val = chunk[2] as f64;
        let gray = (0.299 * r + 0.587 * g + 0.114 * b_val) as u8;
        chunk[0] = gray;
        chunk[1] = gray;
        chunk[2] = gray;
    }
}

/// 反转颜色
#[wasm_bindgen]
pub fn invert(pixels: &mut [u8]) {
    for i in 0..pixels.len() {
        if (i + 1) % 4 != 0 {
            // 不处理 alpha 通道
            pixels[i] = 255 - pixels[i];
        }
    }
}

/// 字符串翻转
#[wasm_bindgen]
pub fn reverse_string(s: &str) -> String {
    s.chars().rev().collect()
}
