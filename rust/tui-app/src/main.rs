//! Rust TUI 实战
//! 基于 ratatui + crossterm 的终端任务管理器

use chrono::Local;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Terminal,
};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Task {
    id: usize,
    title: String,
    done: bool,
    created_at: String,
}

struct App {
    tasks: Vec<Task>,
    input: String,
    input_mode: InputMode,
    selected: usize,
    next_id: usize,
}

#[derive(PartialEq)]
enum InputMode {
    Normal,
    Adding,
}

impl App {
    fn new() -> Self {
        let tasks = load_tasks().unwrap_or_default();
        let next_id = tasks.iter().map(|t| t.id).max().unwrap_or(0) + 1;
        App {
            tasks,
            input: String::new(),
            input_mode: InputMode::Normal,
            selected: 0,
            next_id,
        }
    }

    fn add_task(&mut self) {
        let title = self.input.trim().to_string();
        if !title.is_empty() {
            self.tasks.push(Task {
                id: self.next_id,
                title,
                done: false,
                created_at: Local::now().format("%Y-%m-%d %H:%M").to_string(),
            });
            self.next_id += 1;
            save_tasks(&self.tasks);
        }
        self.input.clear();
        self.input_mode = InputMode::Normal;
    }

    fn toggle_task(&mut self) {
        if let Some(task) = self.tasks.get_mut(self.selected) {
            task.done = !task.done;
            save_tasks(&self.tasks);
        }
    }

    fn delete_task(&mut self) {
        if self.selected < self.tasks.len() {
            self.tasks.remove(self.selected);
            if self.selected >= self.tasks.len() && !self.tasks.is_empty() {
                self.selected = self.tasks.len() - 1;
            }
            save_tasks(&self.tasks);
        }
    }

    fn move_down(&mut self) {
        if !self.tasks.is_empty() && self.selected < self.tasks.len() - 1 {
            self.selected += 1;
        }
    }

    fn move_up(&mut self) {
        if self.selected > 0 {
            self.selected -= 1;
        }
    }
}

fn data_dir() -> PathBuf {
    let mut path = dirs::data_dir().unwrap_or_else(|| PathBuf::from("."));
    path.push("lili-tui");
    fs::create_dir_all(&path).ok();
    path.push("tasks.json");
    path
}

fn load_tasks() -> Option<Vec<Task>> {
    let path = data_dir();
    if path.exists() {
        let data = fs::read_to_string(&path).ok()?;
        serde_json::from_str(&data).ok()
    } else {
        None
    }
}

fn save_tasks(tasks: &[Task]) {
    let path = data_dir();
    if let Ok(json) = serde_json::to_string_pretty(tasks) {
        fs::write(path, json).ok();
    }
}

fn main() -> io::Result<()> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut app = App::new();
    let res = run_app(&mut terminal, &mut app);

    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;
    res
}

fn run_app(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    app: &mut App,
) -> io::Result<()> {
    loop {
        terminal.draw(|f| ui(f, app))?;

        if let Event::Key(key) = event::read()? {
            match app.input_mode {
                InputMode::Normal => match key.code {
                    KeyCode::Char('q') => return Ok(()),
                    KeyCode::Char('a') => app.input_mode = InputMode::Adding,
                    KeyCode::Char(' ') => app.toggle_task(),
                    KeyCode::Char('d') => app.delete_task(),
                    KeyCode::Down | KeyCode::Char('j') => app.move_down(),
                    KeyCode::Up | KeyCode::Char('k') => app.move_up(),
                    _ => {}
                },
                InputMode::Adding => match key.code {
                    KeyCode::Enter => app.add_task(),
                    KeyCode::Esc => {
                        app.input.clear();
                        app.input_mode = InputMode::Normal;
                    }
                    KeyCode::Char(c) => app.input.push(c),
                    KeyCode::Backspace => {
                        app.input.pop();
                    }
                    _ => {}
                },
            }
        }
    }
}

fn ui(f: &mut ratatui::Frame, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .margin(1)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(1),
            Constraint::Length(3),
        ])
        .split(f.area());

    // Title
    let title = Paragraph::new("📋 立里任务管理器")
        .style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD))
        .block(Block::default().borders(Borders::ALL));
    f.render_widget(title, chunks[0]);

    // Task list
    let items: Vec<ListItem> = app
        .tasks
        .iter()
        .enumerate()
        .map(|(i, task)| {
            let (icon, style) = if task.done {
                ("✅", Style::default().fg(Color::Green))
            } else {
                ("⬜", Style::default().fg(Color::Yellow))
            };

            let line = Line::from(vec![
                Span::styled(format!("{} ", icon), style),
                Span::styled(
                    format!("{}  [{}]", task.title, task.created_at),
                    if i == app.selected {
                        Style::default()
                            .fg(Color::Black)
                            .bg(Color::White)
                            .add_modifier(Modifier::BOLD)
                    } else {
                        Style::default()
                    },
                ),
            ]);
            ListItem::new(line)
        })
        .collect();

    let list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title("任务列表"))
        .highlight_style(Style::default());
    f.render_widget(list, chunks[1]);

    // Status bar
    let status = match app.input_mode {
        InputMode::Normal => {
            format!(
                " a:添加  Space:切换  d:删除  j/k:移动  q:退出 | 共 {} 个任务",
                app.tasks.len()
            )
        }
        InputMode::Adding => {
            format!(" 输入任务名称: {}  (Enter确认, Esc取消)", app.input)
        }
    };
    let status_bar = Paragraph::new(status)
        .style(Style::default().fg(Color::Gray))
        .block(Block::default().borders(Borders::ALL));
    f.render_widget(status_bar, chunks[2]);
}
