//! Rust 加密工具实战
//! AES-256-GCM 加解密、SHA-256 哈希、Base64 编解码

use aes_gcm::aead::{Aead, KeyInit, OsRng};
use aes_gcm::{Aes256Gcm, Nonce};
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use clap::{Parser, Subcommand};
use rand::Rng;
use sha2::{Digest, Sha256};
use std::fs;

/// 立里加密工具箱
#[derive(Parser)]
#[command(name = "lili-crypto", version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// AES-256-GCM 加密
    Encrypt {
        /// 明文内容或文件路径
        input: String,
        /// 密钥（32字节，base64编码）
        #[arg(short, long)]
        key: String,
        /// 输入是否为文件路径
        #[arg(short = 'f', long)]
        file: bool,
    },
    /// AES-256-GCM 解密
    Decrypt {
        /// 密文内容或文件路径
        input: String,
        /// 密钥（32字节，base64编码）
        #[arg(short, long)]
        key: String,
        /// 输入是否为文件路径
        #[arg(short = 'f', long)]
        file: bool,
    },
    /// 生成随机密钥
    GenKey,
    /// SHA-256 哈希
    Hash {
        /// 要哈希的内容
        input: String,
        /// 输入是否为文件路径
        #[arg(short = 'f', long)]
        file: bool,
    },
    /// Base64 编码
    Encode {
        input: String,
        #[arg(short = 'f', long)]
        file: bool,
    },
    /// Base64 解码
    Decode {
        input: String,
    },
}

fn read_input(input: &str, is_file: bool) -> Vec<u8> {
    if is_file {
        fs::read(input).expect("无法读取文件")
    } else {
        input.as_bytes().to_vec()
    }
}

fn encrypt(plaintext: &[u8], key: &[u8]) -> (Vec<u8>, Vec<u8>) {
    let cipher = Aes256Gcm::new_from_slice(key).expect("无效密钥长度（需要32字节）");
    let mut nonce_bytes = [0u8; 12];
    rand::rngs::OsRng.fill(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher.encrypt(nonce, plaintext).expect("加密失败");
    (ciphertext, nonce_bytes.to_vec())
}

fn decrypt(ciphertext: &[u8], key: &[u8], nonce: &[u8]) -> Vec<u8> {
    let cipher = Aes256Gcm::new_from_slice(key).expect("无效密钥长度（需要32字节）");
    let nonce = Nonce::from_slice(nonce);
    cipher.decrypt(nonce, ciphertext).expect("解密失败")
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Encrypt { input, key, file } => {
            let key_bytes = BASE64.decode(&key).expect("无效的密钥Base64");
            let plaintext = read_input(&input, file);
            let (ciphertext, nonce) = encrypt(&plaintext, &key_bytes);

            // 输出: nonce(base64) + ":" + ciphertext(base64)
            let result = format!("{}:{}", BASE64.encode(&nonce), BASE64.encode(&ciphertext));
            println!("{}", result);
        }
        Commands::Decrypt { input, key, file } => {
            let key_bytes = BASE64.decode(&key).expect("无效的密钥Base64");
            let data = if file {
                fs::read_to_string(&input).expect("无法读取文件")
            } else {
                input
            };

            let parts: Vec<&str> = data.trim().splitn(2, ':').collect();
            if parts.len() != 2 {
                eprintln!("无效的密文格式（应为 nonce:ciphertext）");
                return;
            }

            let nonce = BASE64.decode(parts[0]).expect("无效的nonce");
            let ciphertext = BASE64.decode(parts[1]).expect("无效的密文");
            let plaintext = decrypt(&ciphertext, &key_bytes, &nonce);

            println!("{}", String::from_utf8_lossy(&plaintext));
        }
        Commands::GenKey => {
            let mut key = [0u8; 32];
            rand::rngs::OsRng.fill(&mut key);
            println!("{}", BASE64.encode(&key));
            println!("\n⚠️  请妥善保管此密钥！");
        }
        Commands::Hash { input, file } => {
            let data = read_input(&input, file);
            let mut hasher = Sha256::new();
            hasher.update(&data);
            let result = hasher.finalize();
            println!("{}", hex::encode(result));
        }
        Commands::Encode { input, file } => {
            let data = read_input(&input, file);
            println!("{}", BASE64.encode(&data));
        }
        Commands::Decode { input } => {
            let data = BASE64.decode(input.trim()).expect("无效的Base64输入");
            println!("{}", String::from_utf8_lossy(&data));
        }
    }
}
