//! Rust 数据库实战
//! SQLite CRUD 操作、事务处理、连接池模拟

use clap::{Parser, Subcommand};
use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use std::fs;

#[derive(Debug, Serialize, Deserialize)]
struct Book {
    id: Option<i64>,
    title: String,
    author: String,
    year: i32,
    isbn: String,
}

#[derive(Parser)]
#[command(name = "lili-db")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// 初始化数据库
    Init,
    /// 添加图书
    Add {
        title: String,
        author: String,
        year: i32,
        isbn: String,
    },
    /// 列出所有图书
    List {
        #[arg(short, long)]
        json: bool,
    },
    /// 搜索图书
    Search {
        keyword: String,
    },
    /// 更新图书
    Update {
        id: i64,
        #[arg(short, long)]
        title: Option<String>,
        #[arg(short, long)]
        author: Option<String>,
        #[arg(short, long)]
        year: Option<i32>,
    },
    /// 删除图书
    Delete {
        id: i64,
    },
}

const DB_PATH: &str = "books.db";

fn get_conn() -> Connection {
    Connection::open(DB_PATH).expect("无法打开数据库")
}

fn init_db() {
    let conn = get_conn();
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            year INTEGER NOT NULL,
            isbn TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );"
    ).expect("数据库初始化失败");
    println!("✅ 数据库已初始化: {}", DB_PATH);
}

fn add_book(book: &Book) {
    let conn = get_conn();
    conn.execute(
        "INSERT INTO books (title, author, year, isbn) VALUES (?1, ?2, ?3, ?4)",
        params![book.title, book.author, book.year, book.isbn],
    ).expect("添加失败");
    println!("✅ 已添加: 《{}》", book.title);
}

fn list_books(as_json: bool) {
    let conn = get_conn();
    let mut stmt = conn
        .prepare("SELECT id, title, author, year, isbn FROM books ORDER BY id")
        .expect("查询失败");

    let books: Vec<Book> = stmt
        .query_map([], |row| {
            Ok(Book {
                id: row.get(0)?,
                title: row.get(1)?,
                author: row.get(2)?,
                year: row.get(3)?,
                isbn: row.get(4)?,
            })
        })
        .expect("映射失败")
        .filter_map(|r| r.ok())
        .collect();

    if as_json {
        println!("{}", serde_json::to_string_pretty(&books).unwrap());
    } else {
        if books.is_empty() {
            println!("📚 暂无图书");
        }
        for book in &books {
            println!(
                "  [{}] 《{}》 {} ({}) ISBN: {}",
                book.id.unwrap_or(0),
                book.title,
                book.author,
                book.year,
                book.isbn
            );
        }
        println!("---\n共 {} 本", books.len());
    }
}

fn search_books(keyword: &str) {
    let conn = get_conn();
    let mut stmt = conn
        .prepare(
            "SELECT id, title, author, year, isbn FROM books
             WHERE title LIKE ?1 OR author LIKE ?1
             ORDER BY id",
        )
        .expect("查询失败");

    let pattern = format!("%{}%", keyword);
    let books: Vec<Book> = stmt
        .query_map(params![pattern], |row| {
            Ok(Book {
                id: row.get(0)?,
                title: row.get(1)?,
                author: row.get(2)?,
                year: row.get(3)?,
                isbn: row.get(4)?,
            })
        })
        .expect("映射失败")
        .filter_map(|r| r.ok())
        .collect();

    for book in &books {
        println!("  [{}] 《{}》 {} ({})", book.id.unwrap_or(0), book.title, book.author, book.year);
    }
    println!("找到 {} 本匹配 \"{}\"", books.len(), keyword);
}

fn update_book(id: i64, title: Option<String>, author: Option<String>, year: Option<i32>) {
    let conn = get_conn();
    let mut updates = Vec::new();
    let mut params_vec: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();

    if let Some(t) = title {
        updates.push("title = ?");
        params_vec.push(Box::new(t));
    }
    if let Some(a) = author {
        updates.push("author = ?");
        params_vec.push(Box::new(a));
    }
    if let Some(y) = year {
        updates.push("year = ?");
        params_vec.push(Box::new(y));
    }

    if updates.is_empty() {
        println!("未指定更新字段");
        return;
    }

    let sql = format!("UPDATE books SET {} WHERE id = ?", updates.join(", "));
    params_vec.push(Box::new(id));

    let param_refs: Vec<&dyn rusqlite::types::ToSql> = params_vec.iter().map(|p| p.as_ref()).collect();
    let affected = conn.execute(&sql, param_refs.as_slice()).expect("更新失败");

    if affected > 0 {
        println!("✅ 已更新图书 id={}", id);
    } else {
        println!("未找到图书 id={}", id);
    }
}

fn delete_book(id: i64) {
    let conn = get_conn();
    let affected = conn
        .execute("DELETE FROM books WHERE id = ?1", params![id])
        .expect("删除失败");
    if affected > 0 {
        println!("✅ 已删除图书 id={}", id);
    } else {
        println!("未找到图书 id={}", id);
    }
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Init => init_db(),
        Commands::Add { title, author, year, isbn } => {
            add_book(&Book { id: None, title, author, year, isbn });
        }
        Commands::List { json } => list_books(json),
        Commands::Search { keyword } => search_books(&keyword),
        Commands::Update { id, title, author, year } => {
            update_book(id, title, author, year);
        }
        Commands::Delete { id } => delete_book(id),
    }
}
