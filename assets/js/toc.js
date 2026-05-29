/**
 * Table of Contents Generator
 * 포스트의 헤딩 태그들을 자동으로 감지하여 목차를 생성합니다.
 */

class TableOfContents {
    constructor() {
        this.tocButton = null;
        this.tocDropdown = null;
        this.headings = [];
        this.activeHeading = null;
        this.isOpen = false;
        this.init();
    }

    init() {
        // 포스트 콘텐츠가 있는지 확인
        const postContent = document.querySelector('.post-full-content');
        if (!postContent) return;

        // 헤딩 요소들 수집
        this.collectHeadings(postContent);

        // 헤딩이 2개 이상 있을 때만 TOC 생성
        if (this.headings.length >= 2) {
            this.createTOCButton();
            this.addScrollListener();
            this.addClickListeners();
            this.addOutsideClickListener();
        }
    }

    collectHeadings(container) {
        const headingSelectors = 'h1, h2, h3, h4, h5, h6';
        const headingElements = container.querySelectorAll(headingSelectors);

        headingElements.forEach((heading, index) => {
            // ID가 없으면 생성
            if (!heading.id) {
                heading.id = this.generateId(heading.textContent, index);
            }

            this.headings.push({
                element: heading,
                id: heading.id,
                text: heading.textContent.trim(),
                level: parseInt(heading.tagName.charAt(1)),
                offsetTop: heading.offsetTop
            });
        });
    }

    generateId(text, index) {
        // 텍스트를 URL 친화적인 ID로 변환
        let id = text
            .toLowerCase()
            .replace(/[^\w\s-]/g, '') // 특수문자 제거
            .replace(/\s+/g, '-') // 공백을 하이픈으로
            .replace(/-+/g, '-') // 연속 하이픈 제거
            .trim();

        // 빈 ID인 경우 기본값 사용
        if (!id) {
            id = `heading-${index}`;
        }

        return id;
    }

    createTOCButton() {
        // TOC 플로팅 버튼 생성
        this.tocButton = document.createElement('button');
        this.tocButton.id = 'toc-floating-btn';
        this.tocButton.className = 'toc-floating-btn';
        this.tocButton.innerHTML = '📋';
        this.tocButton.setAttribute('aria-label', '목차 보기');
        this.tocButton.setAttribute('title', '목차');

        // TOC 사이드바 생성
        this.tocDropdown = document.createElement('div');
        this.tocDropdown.className = 'toc-sidebar';
        this.tocDropdown.innerHTML = `
            <div class="toc-sidebar-header">
                <h4>목차</h4>
                <span class="toc-count">${this.headings.length}개 항목</span>
                <button class="toc-close-btn" aria-label="목차 닫기">×</button>
            </div>
            <nav class="toc-sidebar-nav">
                <ul class="toc-sidebar-list">
                    ${this.generateTOCItems()}
                </ul>
            </nav>
        `;

        // 포스트 레이아웃에 맞춰 데스크톱에서는 본문 왼쪽 sticky 컬럼으로 배치
        const postInner = document.querySelector('.post-template .site-main > .inner');
        const postArticle = postInner ? postInner.querySelector('.post-full') : null;

        document.body.appendChild(this.tocButton);
        if (postInner && postArticle) {
            postInner.insertBefore(this.tocDropdown, postArticle);
            postInner.classList.add('has-toc');
        } else {
            document.body.appendChild(this.tocDropdown);
        }

        // 버튼 클릭 이벤트
        this.tocButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleSidebar();
        });

        // 닫기 버튼 이벤트
        const closeBtn = this.tocDropdown.querySelector('.toc-close-btn');
        closeBtn.addEventListener('click', () => {
            this.hideSidebar();
        });
    }

    toggleSidebar() {
        this.isOpen = !this.isOpen;

        if (this.isOpen) {
            this.showSidebar();
        } else {
            this.hideSidebar();
        }
    }

    showSidebar() {
        this.tocDropdown.classList.add('show');
        this.tocButton.classList.add('active');
        document.body.classList.add('toc-sidebar-open');

        // 현재 활성 헤딩으로 스크롤
        this.scrollToActiveItem();
    }

    hideSidebar() {
        this.tocDropdown.classList.remove('show');
        this.tocButton.classList.remove('active');
        document.body.classList.remove('toc-sidebar-open');
    }

    scrollToActiveItem() {
        const activeLink = this.tocDropdown.querySelector('.toc-link.active');
        if (activeLink) {
            activeLink.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });
        }
    }

    addOutsideClickListener() {
        // 오버레이 클릭으로 사이드바 닫기
        document.addEventListener('click', (e) => {
            if (this.isOpen &&
                !this.tocButton.contains(e.target) &&
                !this.tocDropdown.contains(e.target)) {
                this.hideSidebar();
            }
        });

        // ESC 키로 사이드바 닫기
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.hideSidebar();
            }
        });
    }

    generateTOCItems() {
        return this.headings.map((heading) => {
            const level = heading.level;
            return `
                <li class="toc-item toc-level-${level}">
                    <a href="#${heading.id}" class="toc-link" data-heading-id="${heading.id}">
                        ${heading.text}
                    </a>
                </li>
            `;
        }).join('');
    }

    addClickListeners() {
        const nav = this.tocDropdown.querySelector('.toc-sidebar-nav');
        nav.addEventListener('click', (e) => {
            const link = e.target.closest('.toc-link');
            if (!link) return;

            e.preventDefault();
            const targetId = link.getAttribute('data-heading-id');
            const targetElement = document.getElementById(targetId);

            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });

                history.replaceState(null, null, `#${targetId}`);

                if (window.innerWidth <= 1320) {
                    this.hideSidebar();
                }
            }
        });
    }

    addScrollListener() {
        let ticking = false;

        const updateActiveHeading = () => {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            let activeHeading = null;

            // 현재 스크롤 위치에서 가장 가까운 헤딩 찾기
            for (let i = this.headings.length - 1; i >= 0; i--) {
                const heading = this.headings[i];
                if (scrollTop >= heading.element.offsetTop - 100) {
                    activeHeading = heading;
                    break;
                }
            }

            // 활성 헤딩 업데이트
            if (activeHeading && activeHeading !== this.activeHeading) {
                this.updateActiveLink(activeHeading.id);
                this.activeHeading = activeHeading;
            }

            ticking = false;
        };

        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(updateActiveHeading);
                ticking = true;
            }
        });

        // 초기 활성 헤딩 설정
        updateActiveHeading();
    }

    updateActiveLink(activeId) {
        if (!this.tocDropdown) return;

        // 모든 링크에서 active 클래스 제거
        const allLinks = this.tocDropdown.querySelectorAll('.toc-link');
        allLinks.forEach(link => link.classList.remove('active'));

        // 현재 활성 링크에 active 클래스 추가
        const activeLink = this.tocDropdown.querySelector(`[data-heading-id="${activeId}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
    }
}

// DOM이 로드되면 TOC 초기화
document.addEventListener('DOMContentLoaded', () => {
    new TableOfContents();
});
