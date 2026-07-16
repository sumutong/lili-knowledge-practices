//! Rust Web API 实战
//! 基于 Actix-web 的 RESTful API，提供用户 CRUD 操作

use actix_web::{web, App, HttpResponse, HttpServer, middleware};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;
use uuid::Uuid;
use chrono::Utc;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct User {
    id: String,
    name: String,
    email: String,
    created_at: String,
}

#[derive(Debug, Deserialize)]
struct CreateUser {
    name: String,
    email: String,
}

#[derive(Debug, Deserialize)]
struct UpdateUser {
    name: Option<String>,
    email: Option<String>,
}

struct AppState {
    users: Mutex<HashMap<String, User>>,
}

async fn health() -> HttpResponse {
    HttpResponse::Ok().json(serde_json::json!({
        "status": "ok",
        "service": "lili-web-api",
        "version": "0.1.0"
    }))
}

async fn list_users(data: web::Data<AppState>) -> HttpResponse {
    let users = data.users.lock().unwrap();
    let user_list: Vec<&User> = users.values().collect();
    HttpResponse::Ok().json(user_list)
}

async fn get_user(
    data: web::Data<AppState>,
    path: web::Path<String>,
) -> HttpResponse {
    let users = data.users.lock().unwrap();
    match users.get(&path.into_inner()) {
        Some(user) => HttpResponse::Ok().json(user),
        None => HttpResponse::NotFound().json(serde_json::json!({
            "error": "用户不存在"
        })),
    }
}

async fn create_user(
    data: web::Data<AppState>,
    body: web::Json<CreateUser>,
) -> HttpResponse {
    let mut users = data.users.lock().unwrap();
    let id = Uuid::new_v4().to_string();
    let user = User {
        id: id.clone(),
        name: body.name.clone(),
        email: body.email.clone(),
        created_at: Utc::now().to_rfc3339(),
    };
    users.insert(id, user.clone());
    HttpResponse::Created().json(user)
}

async fn update_user(
    data: web::Data<AppState>,
    path: web::Path<String>,
    body: web::Json<UpdateUser>,
) -> HttpResponse {
    let mut users = data.users.lock().unwrap();
    let user_id = path.into_inner();

    match users.get_mut(&user_id) {
        Some(user) => {
            if let Some(name) = &body.name {
                user.name = name.clone();
            }
            if let Some(email) = &body.email {
                user.email = email.clone();
            }
            HttpResponse::Ok().json(user.clone())
        }
        None => HttpResponse::NotFound().json(serde_json::json!({
            "error": "用户不存在"
        })),
    }
}

async fn delete_user(
    data: web::Data<AppState>,
    path: web::Path<String>,
) -> HttpResponse {
    let mut users = data.users.lock().unwrap();
    match users.remove(&path.into_inner()) {
        Some(_) => HttpResponse::Ok().json(serde_json::json!({
            "message": "用户已删除"
        })),
        None => HttpResponse::NotFound().json(serde_json::json!({
            "error": "用户不存在"
        })),
    }
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("🚀 立里 Web API 启动于 http://127.0.0.1:8080");

    let app_state = web::Data::new(AppState {
        users: Mutex::new(HashMap::new()),
    });

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .wrap(middleware::Logger::default())
            .service(
                web::scope("/api/v1")
                    .route("/health", web::get().to(health))
                    .route("/users", web::get().to(list_users))
                    .route("/users", web::post().to(create_user))
                    .route("/users/{id}", web::get().to(get_user))
                    .route("/users/{id}", web::put().to(update_user))
                    .route("/users/{id}", web::delete().to(delete_user))
            )
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}
