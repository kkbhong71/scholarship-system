import os
import csv
import io
import hashlib
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ─── Database Config ───
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///scholarship.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'oseong-scholarship-2026')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # 8시간 후 자동 로그아웃

db = SQLAlchemy(app)

# ═══════════════════════════════════════════
#  Models
# ═══════════════════════════════════════════

class Manager(db.Model):
    __tablename__ = 'managers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), default='')
    contact = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'role': self.role,
            'department': self.department or '', 'contact': self.contact or ''
        }

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    class_num = db.Column(db.Integer, nullable=False)
    student_num = db.Column(db.Integer, default=0)
    gender = db.Column(db.String(10), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payments = db.relationship('Payment', backref='student', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'grade': self.grade,
            'class_num': self.class_num, 'student_num': self.student_num,
            'gender': self.gender or ''
        }

class Scholarship(db.Model):
    __tablename__ = 'scholarships'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    provider = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payments = db.relationship('Payment', backref='scholarship', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'provider': self.provider,
            'category': self.category, 'amount': self.amount or 0,
            'description': self.description or ''
        }

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarships.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    pay_date = db.Column(db.String(20), default='')
    year = db.Column(db.Integer, default=2026)
    status = db.Column(db.String(20), default='지급예정')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        st = Student.query.get(self.student_id)
        sc = Scholarship.query.get(self.scholarship_id)
        return {
            'id': self.id, 'student_id': self.student_id,
            'scholarship_id': self.scholarship_id,
            'amount': self.amount, 'pay_date': self.pay_date or '',
            'year': self.year, 'status': self.status,
            'student_name': st.name if st else '삭제됨',
            'student_grade': st.grade if st else 0,
            'student_class': st.class_num if st else 0,
            'student_num': st.student_num if st else 0,
            'scholarship_name': sc.name if sc else '삭제됨',
            'scholarship_provider': sc.provider if sc else '',
            'scholarship_category': sc.category if sc else '',
        }

class Regulation(db.Model):
    __tablename__ = 'regulations'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='오성중학교 장학금 지급 규정')
    content = db.Column(db.Text, nullable=False)
    effective_date = db.Column(db.String(20), default='2026-03-01')
    last_modified = db.Column(db.String(20), default='2026-03-01')

    def to_dict(self):
        return {
            'id': self.id, 'title': self.title, 'content': self.content,
            'effective_date': self.effective_date, 'last_modified': self.last_modified
        }


class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

def hash_password(pw):
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

# ─── 인증 데코레이터 ───
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': '로그인이 필요합니다'}), 401
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════
#  기본 규정 데이터
# ═══════════════════════════════════════════

DEFAULT_REGULATION = """【제1장 총칙】

제1조 (목적)
이 규정은 오성중학교(이하 "본교"라 한다) 재학생에 대한 장학금 지급에 관한 기준과 절차를 정함을 목적으로 한다.

제2조 (적용 범위)
이 규정은 본교에 재학 중인 전 학년(1~3학년) 학생에게 적용한다.

제3조 (장학금의 종류)
본교에서 운영하는 장학금의 종류는 다음 각 호와 같다.
① 성적우수 장학금: 학업 성적이 우수한 학생에게 지급
② 생활곤란 장학금: 경제적으로 어려운 학생에게 지급
③ 특기적성 장학금: 예체능 등 특기 분야에서 우수한 학생에게 지급
④ 봉사활동 장학금: 봉사활동 실적이 우수한 학생에게 지급
⑤ 리더십 장학금: 학교생활에서 리더십을 발휘한 학생에게 지급
⑥ 기타 장학금: 외부 기관·단체·개인이 지정하여 지급하는 장학금

제4조 (재원)
장학금의 재원은 다음 각 호로 한다.
① 학교 자체 예산
② 교육청 지원금
③ 지방자치단체 보조금
④ 외부 장학재단 및 기업 후원금
⑤ 개인 기부금
⑥ 기타 수입

【제2장 선발 기준】

제5조 (성적우수 장학금 선발 기준)
① 직전 학기 교과 성적 상위 10% 이내인 자
② 출석률 95% 이상인 자
③ 학교생활 태도가 모범적인 자
④ 징계 이력이 없는 자

제6조 (생활곤란 장학금 선발 기준)
① 국민기초생활수급자 가정의 자녀
② 차상위계층 가정의 자녀
③ 한부모가정 자녀
④ 다문화가정 자녀
⑤ 기타 학교장이 경제적 지원이 필요하다고 인정하는 자

제7조 (특기적성 장학금 선발 기준)
① 교내·외 대회 입상 실적이 있는 자
② 예체능 분야 특기가 우수하여 담당교사의 추천을 받은 자
③ 과학·정보·발명 등 특기 분야에서 두각을 나타낸 자

제8조 (봉사활동 장학금 선발 기준)
① 해당 학기 봉사활동 시간이 20시간 이상인 자
② 지역사회 봉사활동에 적극 참여한 자
③ 학교 자치활동에 헌신적으로 기여한 자

제9조 (리더십 장학금 선발 기준)
① 학생회 임원으로 활동한 자
② 학급 회장·부회장으로 모범적으로 활동한 자
③ 학교 행사 기획 및 운영에 주도적으로 참여한 자

【제3장 지급 절차】

제10조 (신청 및 추천)
① 장학금 대상자는 담임교사 또는 해당 부서장의 추천을 받아야 한다.
② 생활곤란 장학금은 학생 본인 또는 보호자가 직접 신청할 수 있다.
③ 외부 장학금은 해당 기관의 절차에 따른다.

제11조 (심사)
① 장학금 심사는 장학금심사위원회에서 실시한다.
② 장학금심사위원회는 교감을 위원장으로 하고, 각 학년부장, 교무부장, 생활지도부장으로 구성한다.
③ 위원회는 재적위원 과반수의 출석으로 개회하고, 출석위원 과반수의 찬성으로 의결한다.

제12조 (지급 시기)
① 장학금은 매 학기 1회 이상 지급함을 원칙으로 한다.
② 성적우수 장학금: 학기말 성적 확정 후 1개월 이내
③ 생활곤란 장학금: 수시 지급 가능
④ 기타 장학금: 해당 사유 발생 후 적정 시기에 지급

제13조 (지급 방법)
① 장학금은 학생 본인 또는 보호자 명의 계좌로 입금함을 원칙으로 한다.
② 현금 지급 시 영수증을 반드시 징수한다.
③ 학비감면 형태의 장학금은 해당 금액을 학교회계에서 처리한다.

제14조 (지급 금액)
① 장학금 지급 금액은 매 학년도 초 학교운영위원회의 심의를 거쳐 학교장이 결정한다.
② 동일 학생에게 복수의 장학금을 지급할 수 있으나, 동일 유형의 장학금 중복 지급은 불가한다.
③ 외부 장학금의 금액은 해당 기관의 기준에 따른다.

【제4장 관리 및 보칙】

제15조 (장학금 환수)
다음 각 호에 해당하는 경우 지급된 장학금의 전부 또는 일부를 환수할 수 있다.
① 허위 서류를 제출한 경우
② 장학금 수혜 후 자퇴 또는 제적된 경우
③ 중대한 징계처분을 받은 경우

제16조 (기록 관리)
① 장학금 지급에 관한 일체의 기록은 장학금 담당 부서에서 관리한다.
② 장학금 지급 대장은 3년간 보존한다.
③ 개인정보 보호법에 따라 학생의 개인정보를 보호하여야 한다.

제17조 (보고)
장학금 담당자는 매 학기 말 장학금 지급 현황을 학교장에게 보고하여야 한다.

제18조 (규정의 개정)
이 규정의 개정은 학교운영위원회의 심의를 거쳐 학교장이 결정한다.

【부칙】

제1조 (시행일)
이 규정은 2026년 3월 1일부터 시행한다.

제2조 (경과조치)
이 규정 시행 이전에 지급된 장학금에 대해서는 종전의 규정에 따른다."""


# ═══════════════════════════════════════════
#  DB 초기화
# ═══════════════════════════════════════════

def init_db():
    db.create_all()
    if Regulation.query.count() == 0:
        reg = Regulation(
            title='오성중학교 장학금 지급 규정',
            content=DEFAULT_REGULATION,
            effective_date='2026-03-01',
            last_modified='2026-03-01'
        )
        db.session.add(reg)
        db.session.commit()
    # 기본 비밀번호 설정 (최초 1회)
    if not SystemConfig.query.filter_by(key='admin_password').first():
        default_pw = SystemConfig(key='admin_password', value=hash_password('oseong2026'))
        db.session.add(default_pw)
        db.session.commit()

with app.app_context():
    init_db()


# ═══════════════════════════════════════════
#  Routes - 인증
# ═══════════════════════════════════════════

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/auth/check')
def auth_check():
    return jsonify({'logged_in': bool(session.get('logged_in'))})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    pw = data.get('password', '')
    stored = SystemConfig.query.filter_by(key='admin_password').first()
    if stored and stored.value == hash_password(pw):
        session.permanent = True
        session['logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': '비밀번호가 올바르지 않습니다.'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/change_password', methods=['POST'])
@login_required
def change_password():
    data = request.json
    current = data.get('current', '')
    new_pw = data.get('new_password', '')
    confirm = data.get('confirm', '')
    
    stored = SystemConfig.query.filter_by(key='admin_password').first()
    if not stored or stored.value != hash_password(current):
        return jsonify({'success': False, 'error': '현재 비밀번호가 올바르지 않습니다.'}), 400
    if len(new_pw) < 4:
        return jsonify({'success': False, 'error': '새 비밀번호는 4자 이상이어야 합니다.'}), 400
    if new_pw != confirm:
        return jsonify({'success': False, 'error': '새 비밀번호가 일치하지 않습니다.'}), 400
    
    stored.value = hash_password(new_pw)
    db.session.commit()
    return jsonify({'success': True})


# ═══════════════════════════════════════════
#  API - Managers
# ═══════════════════════════════════════════

@app.route('/api/managers', methods=['GET'])
@login_required
def get_managers():
    managers = Manager.query.order_by(Manager.id).all()
    return jsonify([m.to_dict() for m in managers])

@app.route('/api/managers', methods=['POST'])
@login_required
def add_manager():
    data = request.json
    m = Manager(name=data['name'], role=data['role'],
                department=data.get('department', ''), contact=data.get('contact', ''))
    db.session.add(m)
    db.session.commit()
    return jsonify(m.to_dict()), 201

@app.route('/api/managers/<int:id>', methods=['PUT'])
@login_required
def update_manager(id):
    m = Manager.query.get_or_404(id)
    data = request.json
    m.name = data.get('name', m.name)
    m.role = data.get('role', m.role)
    m.department = data.get('department', m.department)
    m.contact = data.get('contact', m.contact)
    db.session.commit()
    return jsonify(m.to_dict())

@app.route('/api/managers/<int:id>', methods=['DELETE'])
@login_required
def delete_manager(id):
    m = Manager.query.get_or_404(id)
    db.session.delete(m)
    db.session.commit()
    return jsonify({'success': True})


# ═══════════════════════════════════════════
#  API - Students
# ═══════════════════════════════════════════

@app.route('/api/students', methods=['GET'])
@login_required
def get_students():
    students = Student.query.order_by(Student.grade, Student.class_num, Student.student_num).all()
    return jsonify([s.to_dict() for s in students])

@app.route('/api/students', methods=['POST'])
@login_required
def add_student():
    data = request.json
    s = Student(name=data['name'], grade=int(data['grade']),
                class_num=int(data['class_num']),
                student_num=int(data.get('student_num', 0)),
                gender=data.get('gender', ''))
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201

@app.route('/api/students/bulk', methods=['POST'])
@login_required
def bulk_add_students():
    data = request.json
    count = 0
    for item in data.get('students', []):
        if not item.get('name'):
            continue
        s = Student(name=item['name'], grade=int(item.get('grade', 1)),
                    class_num=int(item.get('class_num', 1)),
                    student_num=int(item.get('student_num', 0)),
                    gender=item.get('gender', ''))
        db.session.add(s)
        count += 1
    db.session.commit()
    return jsonify({'success': True, 'count': count})

@app.route('/api/students/<int:id>', methods=['PUT'])
@login_required
def update_student(id):
    s = Student.query.get_or_404(id)
    data = request.json
    s.name = data.get('name', s.name)
    s.grade = int(data.get('grade', s.grade))
    s.class_num = int(data.get('class_num', s.class_num))
    s.student_num = int(data.get('student_num', s.student_num))
    s.gender = data.get('gender', s.gender)
    db.session.commit()
    return jsonify(s.to_dict())

@app.route('/api/students/<int:id>', methods=['DELETE'])
@login_required
def delete_student(id):
    s = Student.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/students/delete_all', methods=['DELETE'])
@login_required
def delete_all_students():
    Payment.query.delete()
    Student.query.delete()
    db.session.commit()
    return jsonify({'success': True})


# ═══════════════════════════════════════════
#  API - Scholarships
# ═══════════════════════════════════════════

@app.route('/api/scholarships', methods=['GET'])
@login_required
def get_scholarships():
    scholarships = Scholarship.query.order_by(Scholarship.id).all()
    return jsonify([s.to_dict() for s in scholarships])

@app.route('/api/scholarships', methods=['POST'])
@login_required
def add_scholarship():
    data = request.json
    s = Scholarship(name=data['name'], provider=data['provider'],
                    category=data['category'],
                    amount=int(data.get('amount', 0)),
                    description=data.get('description', ''))
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201

@app.route('/api/scholarships/<int:id>', methods=['PUT'])
@login_required
def update_scholarship(id):
    s = Scholarship.query.get_or_404(id)
    data = request.json
    s.name = data.get('name', s.name)
    s.provider = data.get('provider', s.provider)
    s.category = data.get('category', s.category)
    s.amount = int(data.get('amount', s.amount))
    s.description = data.get('description', s.description)
    db.session.commit()
    return jsonify(s.to_dict())

@app.route('/api/scholarships/<int:id>', methods=['DELETE'])
@login_required
def delete_scholarship(id):
    s = Scholarship.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return jsonify({'success': True})


# ═══════════════════════════════════════════
#  API - Payments
# ═══════════════════════════════════════════

@app.route('/api/payments', methods=['GET'])
@login_required
def get_payments():
    payments = Payment.query.order_by(Payment.pay_date.desc()).all()
    return jsonify([p.to_dict() for p in payments])

@app.route('/api/payments', methods=['POST'])
@login_required
def add_payment():
    data = request.json
    p = Payment(student_id=int(data['student_id']),
                scholarship_id=int(data['scholarship_id']),
                amount=int(data['amount']),
                pay_date=data.get('pay_date', ''),
                year=int(data.get('year', 2026)),
                status=data.get('status', '지급예정'))
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201

@app.route('/api/payments/<int:id>', methods=['PUT'])
@login_required
def update_payment(id):
    p = Payment.query.get_or_404(id)
    data = request.json
    if 'student_id' in data: p.student_id = int(data['student_id'])
    if 'scholarship_id' in data: p.scholarship_id = int(data['scholarship_id'])
    if 'amount' in data: p.amount = int(data['amount'])
    if 'pay_date' in data: p.pay_date = data['pay_date']
    if 'year' in data: p.year = int(data['year'])
    if 'status' in data: p.status = data['status']
    db.session.commit()
    return jsonify(p.to_dict())

@app.route('/api/payments/<int:id>', methods=['DELETE'])
@login_required
def delete_payment(id):
    p = Payment.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/payments/csv')
@login_required
def export_csv():
    payments = Payment.query.order_by(Payment.pay_date.desc()).all()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['날짜', '연도', '학년', '반', '번호', '이름', '장학금명', '지원주체', '카테고리', '금액', '상태'])
    for p in payments:
        d = p.to_dict()
        writer.writerow([
            d['pay_date'], d['year'], d['student_grade'], d['student_class'],
            d['student_num'], d['student_name'], d['scholarship_name'],
            d['scholarship_provider'], d['scholarship_category'],
            d['amount'], d['status']
        ])
    response = Response(output.getvalue(), mimetype='text/csv; charset=utf-8')
    response.headers['Content-Disposition'] = f'attachment; filename=scholarship_payments_{date.today()}.csv'
    return response


@app.route('/api/payments/bulk', methods=['POST'])
@login_required
def bulk_add_payments():
    """CSV 업로드를 통한 지급 내역 일괄 등록 (기존 데이터에 추가만 함)"""
    data = request.json
    rows = data.get('payments', [])
    
    students = Student.query.all()
    scholarships = Scholarship.query.all()
    
    added = 0
    skipped = 0
    errors = []
    
    for i, row in enumerate(rows):
        # 학생 찾기: 이름 + 학년 + 반 + 번호로 매칭
        student_name = row.get('이름', row.get('name', '')).strip()
        student_grade = row.get('학년', row.get('grade', '')).strip()
        student_class = row.get('반', row.get('class', row.get('학급', ''))).strip()
        student_num = row.get('번호', row.get('number', row.get('번', ''))).strip()
        
        scholarship_name = row.get('장학금명', row.get('scholarship', '')).strip()
        amount = row.get('금액', row.get('amount', '0')).strip().replace(',', '')
        pay_date = row.get('날짜', row.get('date', row.get('지급날짜', ''))).strip()
        year = row.get('연도', row.get('year', str(date.today().year))).strip()
        status = row.get('상태', row.get('status', '지급완료')).strip()
        
        if not student_name:
            skipped += 1
            continue
        
        # 학생 매칭 (이름 필수, 학년/반/번호는 보조)
        matched_student = None
        candidates = [s for s in students if s.name == student_name]
        
        if len(candidates) == 1:
            matched_student = candidates[0]
        elif len(candidates) > 1:
            # 동명이인: 학년+반+번호로 추가 매칭
            for c in candidates:
                if (str(c.grade) == str(student_grade) and 
                    str(c.class_num) == str(student_class)):
                    if not student_num or str(c.student_num) == str(student_num):
                        matched_student = c
                        break
            if not matched_student:
                matched_student = candidates[0]  # 첫 번째로 fallback
        
        if not matched_student:
            errors.append(f"{i+1}행: 학생 '{student_name}'을(를) 찾을 수 없습니다.")
            skipped += 1
            continue
        
        # 장학금 매칭
        matched_scholarship = None
        if scholarship_name:
            sc_candidates = [s for s in scholarships if s.name == scholarship_name]
            if sc_candidates:
                matched_scholarship = sc_candidates[0]
            else:
                # 부분 매칭 시도
                sc_candidates = [s for s in scholarships if scholarship_name in s.name or s.name in scholarship_name]
                if sc_candidates:
                    matched_scholarship = sc_candidates[0]
        
        if not matched_scholarship:
            errors.append(f"{i+1}행: 장학금 '{scholarship_name}'을(를) 찾을 수 없습니다.")
            skipped += 1
            continue
        
        # 금액 처리
        try:
            pay_amount = int(float(amount)) if amount else matched_scholarship.amount
        except (ValueError, TypeError):
            pay_amount = matched_scholarship.amount
        
        # 연도 처리
        try:
            pay_year = int(year)
        except (ValueError, TypeError):
            pay_year = date.today().year
        
        # 상태 유효성 검증
        if status not in ['지급예정', '지급완료', '보류', '취소']:
            status = '지급완료'
        
        # 지급 내역 추가
        p = Payment(
            student_id=matched_student.id,
            scholarship_id=matched_scholarship.id,
            amount=pay_amount,
            pay_date=pay_date,
            year=pay_year,
            status=status
        )
        db.session.add(p)
        added += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'added': added,
        'skipped': skipped,
        'errors': errors[:10]  # 최대 10개 오류만 반환
    })


# ═══════════════════════════════════════════
#  API - Statistics
# ═══════════════════════════════════════════

@app.route('/api/stats')
@login_required
def get_stats():
    year = request.args.get('year', None)
    
    students = Student.query.all()
    scholarships = Scholarship.query.all()
    
    pay_query = Payment.query
    if year and year != 'all':
        pay_query = pay_query.filter_by(year=int(year))
    
    all_payments = pay_query.all()
    completed = [p for p in all_payments if p.status == '지급완료']
    
    # Summary
    total_amount = sum(p.amount for p in completed)
    total_payments = len(completed)
    unique_recipients = len(set(p.student_id for p in completed))
    pending = len([p for p in all_payments if p.status == '지급예정'])
    
    # Category stats
    cat_map = {}
    for sc in scholarships:
        if sc.category not in cat_map:
            cat_map[sc.category] = {'category': sc.category, 'scholarship_count': 0, 'count': 0, 'amount': 0, 'recipients': set()}
        cat_map[sc.category]['scholarship_count'] += 1
    
    for p in completed:
        sc = next((s for s in scholarships if s.id == p.scholarship_id), None)
        if sc and sc.category in cat_map:
            cat_map[sc.category]['count'] += 1
            cat_map[sc.category]['amount'] += p.amount
            cat_map[sc.category]['recipients'].add(p.student_id)
    
    category_stats = []
    for v in cat_map.values():
        category_stats.append({**v, 'recipients': len(v['recipients'])})
    
    # Grade stats
    grade_stats = []
    for g in [1, 2, 3]:
        g_students = [s for s in students if s.grade == g]
        g_ids = set(s.id for s in g_students)
        g_payments = [p for p in completed if p.student_id in g_ids]
        g_recipients = len(set(p.student_id for p in g_payments))
        g_amount = sum(p.amount for p in g_payments)
        grade_stats.append({
            'grade': g, 'total_students': len(g_students),
            'count': len(g_payments), 'amount': g_amount,
            'recipients': g_recipients,
            'ratio': round((g_recipients / len(g_students) * 100), 1) if g_students else 0
        })
    
    # Class stats
    class_stats = []
    for g in [1, 2, 3]:
        for c in [1, 2]:
            c_students = [s for s in students if s.grade == g and s.class_num == c]
            c_ids = set(s.id for s in c_students)
            c_payments = [p for p in completed if p.student_id in c_ids]
            c_recipients = len(set(p.student_id for p in c_payments))
            c_amount = sum(p.amount for p in c_payments)
            class_stats.append({
                'grade': g, 'class_num': c,
                'total_students': len(c_students),
                'count': len(c_payments), 'amount': c_amount,
                'recipients': c_recipients,
                'ratio': round((c_recipients / len(c_students) * 100), 1) if c_students else 0
            })
    
    # Student ranking
    student_map = {}
    for p in completed:
        if p.student_id not in student_map:
            student_map[p.student_id] = {'count': 0, 'amount': 0}
        student_map[p.student_id]['count'] += 1
        student_map[p.student_id]['amount'] += p.amount
    
    student_stats = []
    for sid, data in sorted(student_map.items(), key=lambda x: -x[1]['amount']):
        st = next((s for s in students if s.id == sid), None)
        if st:
            student_stats.append({
                'student': st.to_dict(), 'count': data['count'], 'amount': data['amount']
            })
    
    return jsonify({
        'summary': {
            'total_students': len(students),
            'total_scholarships': len(scholarships),
            'total_amount': total_amount,
            'total_payments': total_payments,
            'unique_recipients': unique_recipients,
            'pending': pending,
        },
        'category_stats': category_stats,
        'grade_stats': grade_stats,
        'class_stats': class_stats,
        'student_stats': student_stats,
    })


# ═══════════════════════════════════════════
#  API - Regulation
# ═══════════════════════════════════════════

@app.route('/api/regulation', methods=['GET'])
@login_required
def get_regulation():
    reg = Regulation.query.first()
    if not reg:
        reg = Regulation(title='오성중학교 장학금 지급 규정',
                         content=DEFAULT_REGULATION,
                         effective_date='2026-03-01',
                         last_modified='2026-03-01')
        db.session.add(reg)
        db.session.commit()
    return jsonify(reg.to_dict())

@app.route('/api/regulation', methods=['PUT'])
@login_required
def update_regulation():
    data = request.json
    reg = Regulation.query.first()
    if not reg:
        reg = Regulation()
        db.session.add(reg)
    reg.title = data.get('title', reg.title)
    reg.content = data.get('content', reg.content)
    reg.effective_date = data.get('effective_date', reg.effective_date)
    reg.last_modified = date.today().isoformat()
    db.session.commit()
    return jsonify(reg.to_dict())

@app.route('/api/regulation/reset', methods=['POST'])
@login_required
def reset_regulation():
    reg = Regulation.query.first()
    if reg:
        reg.content = DEFAULT_REGULATION
        reg.title = '오성중학교 장학금 지급 규정'
        reg.effective_date = '2026-03-01'
        reg.last_modified = date.today().isoformat()
    else:
        reg = Regulation(title='오성중학교 장학금 지급 규정',
                         content=DEFAULT_REGULATION,
                         effective_date='2026-03-01',
                         last_modified=date.today().isoformat())
        db.session.add(reg)
    db.session.commit()
    return jsonify(reg.to_dict())


# ═══════════════════════════════════════════
#  API - Dashboard
# ═══════════════════════════════════════════

@app.route('/api/dashboard')
@login_required
def dashboard():
    students = Student.query.all()
    scholarships = Scholarship.query.all()
    payments = Payment.query.all()
    completed = [p for p in payments if p.status == '지급완료']
    
    recent = Payment.query.order_by(Payment.pay_date.desc()).limit(5).all()
    
    return jsonify({
        'total_students': len(students),
        'total_scholarships': len(scholarships),
        'total_payments': len(completed),
        'total_amount': sum(p.amount for p in completed),
        'pending': len([p for p in payments if p.status == '지급예정']),
        'unique_recipients': len(set(p.student_id for p in completed)),
        'recent_payments': [p.to_dict() for p in recent],
        'grade_stats': [
            {
                'grade': g,
                'students': len([s for s in students if s.grade == g]),
                'count': len([p for p in completed if any(s.id == p.student_id and s.grade == g for s in students)]),
                'amount': sum(p.amount for p in completed if any(s.id == p.student_id and s.grade == g for s in students)),
            }
            for g in [1, 2, 3]
        ]
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
