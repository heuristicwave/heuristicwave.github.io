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

        // body에 버튼과 사이드바 추가
        document.body.appendChild(this.tocButton);
        document.body.appendChild(this.tocDropdown);

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
        let tocHTML = '';
        let currentLevel = 0;

        this.headings.forEach((heading, index) => {
            const level = heading.level;

            if (level > currentLevel) {
                // 더 깊은 레벨로 들어감
                for (let i = currentLevel; i < level; i++) {
                    if (i > 0) tocHTML += '<ul class="toc-sublist">';
                }
            } else if (level < currentLevel) {
                // 더 얕은 레벨로 나옴
                for (let i = currentLevel; i > level; i--) {
                    tocHTML += '</ul>';
                }
            }

            tocHTML += `
                <li class="toc-item toc-level-${level}">
                    <a href="#${heading.id}" class="toc-link" data-heading-id="${heading.id}">
                        ${heading.text}
                    </a>
                </li>
            `;

            currentLevel = level;
        });

        // 남은 ul 태그들 닫기
        for (let i = currentLevel; i > 1; i--) {
            tocHTML += '</ul>';
        }

        return tocHTML;
    }

    addClickListeners() {
        // 사이드바가 생성된 후에 링크 이벤트 추가
        setTimeout(() => {
            const tocLinks = this.tocDropdown.querySelectorAll('.toc-link');

            tocLinks.forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const targetId = link.getAttribute('data-heading-id');
                    const targetElement = document.getElementById(targetId);

                    if (targetElement) {
                        // 부드러운 스크롤
                        targetElement.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });

                        // URL 업데이트 (히스토리에 추가하지 않음)
                        history.replaceState(null, null, `#${targetId}`);

                        // 모바일에서는 사이드바 닫기
                        if (window.innerWidth <= 768) {
                            this.hideSidebar();
                        }
                    }
                });
            });
        }, 100);
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