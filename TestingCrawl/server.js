const express = require('express');
const bodyParser = require('body-parser');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const session = require('express-session');
const multer = require('multer'); // multer 추가

const app = express();
const PORT = 3000;

// 파일 저장 설정
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, 'uploads/'); // 파일 업로드 폴더 설정
    },
    filename: (req, file, cb) => {
        const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
        cb(null, uniqueSuffix + '-' + file.originalname); // 파일 이름 설정
    }
});
const upload = multer({ storage: storage });

// 데이터베이스 연결
const db = new sqlite3.Database('./database.sqlite', (err) => {
    if (err) {
        console.error(err.message);
    }
    console.log('Connected to the SQLite database.');
});

// 세션 미들웨어 설정
app.use(session({
    secret: 'your_secret_key',
    resave: false,
    saveUninitialized: true,
}));

// 세션 객체를 모든 뷰에 전달하는 미들웨어
app.use((req, res, next) => {
    res.locals.session = req.session;
    next();
});


// 미들웨어 설정
app.use(bodyParser.urlencoded({ extended: false }));
app.use(express.static(path.join(__dirname, 'public')));
app.set('view engine', 'ejs');


// 데이터베이스 테이블 생성
db.serialize(() => {
    // db 삭제 코드
    //db.run(`DROP TABLE IF EXISTS products`);
    //db.run(`DROP TABLE IF EXISTS posts`);
    //db.run(`DROP TABLE IF EXISTS users`);
    
    // 제품 테이블
    db.run(`CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        author TEXT NOT NULL
    )`);

    // 게시판 테이블
    db.run(`CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        author TEXT NOT NULL
    )`);

    // 사용자 테이블
    db.run(`CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )`);

    // 관리자 계정 생성 (없을 경우에만)
    db.run(`INSERT INTO users (username, password) VALUES ('admin', 'admin')`, (err) => {
        if (err && err.message.includes("UNIQUE constraint failed")) {
            console.log("관리자 계정이 이미 존재합니다.");
        } else if (err) {
            console.error("관리자 계정 생성 오류:", err.message);
        } else {
            console.log("관리자 계정이 생성되었습니다.");
        }
    });
});

// 관리자 권한 확인 미들웨어
function isAdmin(req) {
    return req.session.isAuthenticated && req.session.username === 'admin';
}

// 전체 게시글 삭제
app.post('/posts/deleteAll', (req, res) => {
    if (!isAdmin(req)) {
        return res.status(403).send("관리자 권한이 필요합니다.");
    }

    // 테이블을 삭제하고 다시 생성
    db.serialize(() => {
        db.run(`DROP TABLE IF EXISTS posts`);
        db.run(`CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT,
            filePath TEXT
        )`, (err) => {
            if (err) {
                return res.status(500).send("게시글 초기화 중 오류가 발생했습니다.");
            }
            res.redirect('/posts'); // 전체 삭제 후 게시글 목록으로 이동
        });
    });
});

// 전체 제품 삭제
app.post('/products/deleteAll', (req, res) => {
    if (!isAdmin(req)) {
        return res.status(403).send("관리자 권한이 필요합니다.");
    }

    // 테이블을 삭제하고 다시 생성
    db.serialize(() => {
        db.run(`DROP TABLE IF EXISTS products`);
        db.run(`CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            author TEXT
        )`, (err) => {
            if (err) {
                return res.status(500).send("제품 초기화 중 오류가 발생했습니다.");
            }
            res.redirect('/products'); // 전체 삭제 후 제품 목록으로 이동
        });
    });
});

// 라우트 설정

// 홈 페이지
app.get('/', (req, res) => {
    const username = req.session.username;
    res.render('index', { username });
});


// 로그인 페이지

app.get('/login', (req, res) => {
    // 로그인 페이지 렌더링
    res.render('login', { errorMessage: '' });
});

// 로그인 처리
app.post('/login', (req, res) => {
    const { username, password } = req.body;
   
     // 데이터베이스에서 사용자 조회
     const sql = `SELECT * FROM users WHERE username = '${username}' AND password = '${password}'`;
     db.get(sql, (err, row) => {
         if (err) {
             return res.status(500).send("데이터베이스 오류가 발생했습니다.");
         }
 
         if (row) {
             // 로그인 성공 시
             req.session.isAuthenticated = true;
             req.session.username = username;
             res.redirect('/');
         } else {
             // 로그인 실패 시 errorMessage 포함하여 렌더링
             res.render('login', { errorMessage: "아이디 또는 비밀번호가 잘못되었습니다." });
         }
     });
});

// 로그아웃 처리
app.get('/logout', (req, res) => {
    req.session.destroy((err) => {
        if (err) {
            return res.status(500).send("로그아웃 중 오류가 발생했습니다.");
        }
        res.redirect('/');
    });
});

// 회원가입 페이지
app.get('/register', (req, res) => {
    res.render('register'); // register.ejs 파일을 렌더링합니다.
});


app.post('/register', (req, res) => {
    const { username, password, confirmPassword } = req.body;

    if (password !== confirmPassword) {
        return res.render('register', { errorMessage: "비밀번호가 일치하지 않습니다." });
    }

    // 콘솔에 사용자 정보를 출력
    console.log(`새로운 사용자: ${username}`);

    // 사용자 정보를 users 테이블에 추가
    const sql = `INSERT INTO users (username, password) VALUES (?, ?)`;
    db.run(sql, [username, password], (err) => {
        if (err) {
            if (err.message.includes("UNIQUE constraint failed")) {
                return res.render('register', { errorMessage: "이미 존재하는 사용자 이름입니다." });
            } else {
                return res.status(500).send("데이터베이스 오류가 발생했습니다.");
            }
        }
    });
    
    // 회원가입 후 로그인 페이지로 이동
    res.redirect('/login');
});

// 제품 목록
app.get('/products', (req, res) => {
    const query = req.query.query || ''; // 검색어가 없는 경우 빈 문자열로 기본값 설정
    const page = parseInt(req.query.page) || 1;
    const limit = 15;
    const offset = (page - 1) * limit;

    const sql = `SELECT * FROM products WHERE name LIKE ? OR description LIKE ? LIMIT ? OFFSET ?`;
    const searchQuery = `%${query}%`;

    db.all(sql, [searchQuery, searchQuery, limit, offset], (err, rows) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }

        db.get(`SELECT COUNT(*) AS count FROM products WHERE name LIKE ? OR description LIKE ?`, [searchQuery, searchQuery], (err, result) => {
            if (err) {
                return res.status(500).send("데이터베이스 오류가 발생했습니다.");
            }

            const totalPages = Math.ceil(result.count / limit);
            res.render('products', { products: rows, currentPage: page, totalPages, query });
        });
    });
});


// 제품 추가 폼
app.get('/products/add', (req, res) => {
    res.render('addProduct');
});

// 제품 추가 처리
app.post('/products/add', (req, res) => {
    const { name, description, price } = req.body;
    const author = req.session.isAuthenticated ? req.session.username : 'Guest'; // 로그인 여부에 따라 작성자 설정, 기본값: Guest

    const sql = `INSERT INTO products (name, description, price, author) VALUES (?, ?, ?, ?)`;
    db.run(sql, [name, description, price, author], function (err) {
        if (err) {
            console.error("제품 추가 중 오류:", err.message);
            return res.status(500).send("제품 추가 중 오류가 발생했습니다.");
        }
        res.redirect('/products');
    });
});

// 제품 상세 보기
app.get('/productDetail/:id', (req, res) => {
    const id = req.params.id;
    db.get(`SELECT * FROM products WHERE id = ?`, [id], (err, product) => {
        if (err) {
            console.error("제품 조회 중 오류:", err.message);
            return res.status(500).send("제품 조회 중 오류가 발생했습니다.");
        }
        if (!product) {
            return res.status(404).send("제품을 찾을 수 없습니다.");
        }
        res.render('productDetail', { product });
    });
});

// 제품 수정 폼
app.get('/products/edit/:id', (req, res) => {
    if (!req.session.isAuthenticated) {
        return res.redirect('/login');
    }

    const id = req.params.id;
    db.get(`SELECT * FROM products WHERE id = ?`, [id], (err, product) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }
        if (!product) {
            return res.status(404).send("제품을 찾을 수 없습니다.");
        }
        if (product.author !== req.session.username && !isAdmin(req)) {
            return res.status(403).send("수정 권한이 없습니다.");
        }
        res.render('editProduct', { product });
    });
});

// 제품 수정 처리
app.post('/products/edit/:id', (req, res) => {
    if (!req.session.isAuthenticated) {
        return res.redirect('/login');
    }

    const id = req.params.id;
    const { name, description, price } = req.body;

    db.get(`SELECT * FROM products WHERE id = ?`, [id], (err, product) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }
        if (!product) {
            return res.status(404).send("제품을 찾을 수 없습니다.");
        }
        if (product.author !== req.session.username) {
            return res.status(403).send("수정 권한이 없습니다.");
        }

        db.run(`UPDATE products SET name = ?, description = ?, price = ? WHERE id = ?`, [name, description, price, id], function (err) {
            if (err) {
                return res.status(500).send("제품 수정 중 오류가 발생했습니다.");
            }
            res.redirect('/products');
        });
    });
});

// 제품 삭제
app.post('/products/delete/:id', (req, res) => {
    if (!req.session.isAuthenticated) {
        return res.redirect('/login');
    }

    const id = req.params.id;
    db.get(`SELECT * FROM products WHERE id = ?`, [id], (err, product) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }
        if (!product) {
            return res.status(404).send("제품을 찾을 수 없습니다.");
        }
        if (product.author !== req.session.username && !isAdmin(req)) {
            return res.status(403).send("삭제 권한이 없습니다.");
        }

        db.run(`DELETE FROM products WHERE id = ?`, [id], function (err) {
            if (err) {
                return res.status(500).send("제품 삭제 중 오류가 발생했습니다.");
            }
            res.redirect('/products');
        });
    });
});


// 제품 상세 보기
app.get('/productDetail/:id', (req, res) => {
    const id = req.params.id;
    db.get(`SELECT * FROM products WHERE id = ?`, [id], (err, product) => {
        if (err) {
            console.error("제품 조회 중 오류:", err.message);
            return res.status(500).send("제품 조회 중 오류가 발생했습니다.");
        }
        if (!product) {
            return res.status(404).send("제품을 찾을 수 없습니다.");
        }
        res.render('productDetail', { product });
    });
});


// 게시판 목록
app.get('/posts', (req, res) => {
    const query = req.query.query || ''; // 검색어가 없는 경우 빈 문자열로 기본값 설정
    const page = parseInt(req.query.page) || 1;
    const limit = 15;
    const offset = (page - 1) * limit;

    const sql = `SELECT * FROM posts WHERE title LIKE ? OR content LIKE ? LIMIT ? OFFSET ?`;
    const searchQuery = `%${query}%`;

    db.all(sql, [searchQuery, searchQuery, limit, offset], (err, rows) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }

        db.get(`SELECT COUNT(*) AS count FROM posts WHERE title LIKE ? OR content LIKE ?`, [searchQuery, searchQuery], (err, result) => {
            if (err) {
                return res.status(500).send("데이터베이스 오류가 발생했습니다.");
            }

            const totalPages = Math.ceil(result.count / limit);
            res.render('posts', { posts: rows, currentPage: page, totalPages, query });
        });
    });
});



// 게시글 추가 폼
app.get('/posts/add', (req, res) => {
    res.render('addPost');
});

// 게시글 추가 처리
app.post('/posts/add', upload.single('file'), (req, res) => { // 파일 필드 이름과 동일하게 설정
    const { title, content } = req.body;
    const filePath = req.file ? req.file.path : null; // 파일 경로 저장 (파일 없을 경우 null)
    
    // 비로그인 사용자는 기본값 'Guest'
    const author = req.session.isAuthenticated ? req.session.username : 'Guest';

    // 데이터베이스에 게시글 추가
    const sql = `INSERT INTO posts (title, content, filePath, author) VALUES (?, ?, ?, ?)`;
    db.run(sql, [title, content, filePath, author], function (err) {
        if (err) {
            console.error("게시글 추가 중 오류:", err.message);
            return res.status(500).send("게시글 추가 중 오류가 발생했습니다.");
        }
        res.redirect('/posts');
    });
});

// 게시글 수정 폼
app.get('/posts/edit/:id', (req, res) => {
    if (!req.session.isAuthenticated) {
        return res.redirect('/login');
    }
    const id = req.params.id;
    db.get(`SELECT * FROM posts WHERE id = ?`, [id], (err, post) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }
        if (!post) {
            return res.status(404).send("게시글을 찾을 수 없습니다.");
        }
        if (post.author !== req.session.username && !isAdmin(req)) {
            return res.status(403).send("수정 권한이 없습니다.");
        }
        res.render('editPost', { post });
    });
});

// 게시글 수정 처리
app.post('/posts/edit/:id', upload.single('file'), (req, res) => {
    const { title, content } = req.body;
    const id = req.params.id;
    const filePath = req.file ? req.file.path : null;

    // 기존 게시글 조회
    db.get(`SELECT * FROM posts WHERE id = ?`, [id], (err, post) => {
        if (err) {
            console.error("게시글 조회 중 오류:", err.message);
            return res.status(500).send("게시글 조회 중 오류가 발생했습니다.");
        }
        if (!post) {
            return res.status(404).send("게시글을 찾을 수 없습니다.");
        }

        // 새 파일이 업로드되지 않으면 기존 파일 경로 유지
        const updatedFilePath = filePath || post.filePath;

        // 게시글 업데이트
        const sql = `UPDATE posts SET title = ?, content = ?, filePath = ? WHERE id = ?`;
        db.run(sql, [title, content, updatedFilePath, id], function (err) {
            if (err) {
                console.error("게시글 수정 중 오류:", err.message);
                return res.status(500).send("게시글 수정 중 오류가 발생했습니다.");
            }
            res.redirect(`/postDetail/${id}`);
        });
    });
});


// 게시글 삭제
app.post('/posts/delete/:id', (req, res) => {
    if (!req.session.isAuthenticated) {
        return res.redirect('/login');
    }

    const id = req.params.id;
    db.get(`SELECT * FROM posts WHERE id = ?`, [id], (err, post) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }
        if (!post) {
            return res.status(404).send("게시글을 찾을 수 없습니다.");
        }
        if (post.author !== req.session.username && !isAdmin(req)) {
            return res.status(403).send("삭제 권한이 없습니다.");
        }

        db.run(`DELETE FROM posts WHERE id = ?`, [id], function (err) {
            if (err) {
                return res.status(500).send("게시글 삭제 중 오류가 발생했습니다.");
            }
            res.redirect('/posts');
        });
    });
});


// 게시글 상세 보기
app.get('/postDetail/:id', (req, res) => {
    const id = req.params.id;
    db.get(`SELECT * FROM posts WHERE id = ?`, [id], (err, post) => {
        if (err) {
            console.error("게시글 조회 중 오류:", err.message);
            return res.status(500).send("게시글 조회 중 오류가 발생했습니다.");
        }
        if (!post) {
            return res.status(404).send("게시글을 찾을 수 없습니다.");
        }
        res.render('postDetail', { post });
    });
});

// 검색
// 제품 검색
app.get('/products/search', (req, res) => {
    const query = decodeURIComponent(req.query.query || '');
    const sql = `SELECT * FROM products WHERE name LIKE ? OR description LIKE ? LIMIT 15`;
    const params = [`%${query}%`, `%${query}%`];
    db.all(sql, params, (err, products) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }
        res.render('products', {
            products: products,
            query: query,
            totalPages: Math.ceil(products.length / 15),
            currentPage: 1
        });
    });
});

// 게시글 검색
app.get('/posts/search', (req, res) => {
    const query = decodeURIComponent(req.query.query || '');
    const sql = `SELECT * FROM posts WHERE title LIKE ? OR content LIKE ? LIMIT 15`;
    const params = [`%${query}%`, `%${query}%`];
    db.all(sql, params, (err, posts) => {
        if (err) {
            return res.status(500).send("데이터베이스 오류가 발생했습니다.");
        }
        res.render('posts', {
            posts: posts,
            query: query,
            totalPages: Math.ceil(posts.length / 15),
            currentPage: 1
        });
    });
});



// 서버 시작
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
