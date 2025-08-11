# GitHub 至 Gitea 镜像同步

该工具用于设置并管理从GitHub仓库到Gitea仓库的拉取镜像，包括完整的代码库、问题、拉取请求、版本发布及维基内容。

我一直在热切地期待着[Gitea's PR 20311](https://github.com/go-gitea/gitea/pull/20311)已经超过一年了，但由于每次发布都被推迟，我决定在此期间先做些东西出来。

> **直白声明：** 本项目仅为业余爱好而作，期待上方PR能早日合并实现。届时，该项目便完成了使命。本人从零开始搭建了[Cursor](https://cursor.com/)并且[Claude 3.7 Sonnet](https://www.anthropic.com/claude/sonnet).

![Main screenshot](images/main.png)

## 特点

- 用于管理镜像和查看日志的网页界面[screens and more info](#web-ui)
- 在Gitea中设置GitHub仓库为拉取镜像
- 完整镜像代码库、问题及PR（不仅限于发布版本）
- 镜像GitHub版本及发布资源，包含完整描述与附件
- 将GitHub的wiki镜像到独立的Gitea仓库
- 自动发现Gitea中的镜像仓库
- 支持完整的 GitHub URL 和 owner/repo 格式
- 全面日志记录，错误信息中可直接跳转至日志
- 支持具有动态超时的大版本资源发布
- 基于大小的超时计算的资产下载与上传
- 定时镜像，间隔可配置
- 增强版用户界面，带有配置选项的复选框
- 深色模式支持
- 错误处理与可见性

## 快速入门

快速上手，只需几分钟：

```bash
# Clone the repository
git clone https://github.com/jonasrosland/gitmirror.git
cd gitmirror

# Copy and configure the example .env file
cp .env.example .env
# Edit the .env file with your tokens and Gitea URL

# Start the application
docker-compose up -d

# Access the web UI
# Open http://localhost:5000 in your browser
```

## 前提条件

- Docker 和 Docker Compose（用于运行应用程序）
- GitHub个人访问令牌附带`repo`范围
- Gitea 访问令牌附带`read:user`, `write:repository`，以及`write:issue`范围
- 访问GitHub和Gitea代码仓库

## 配置

创建一个`.env`在与docker-compose.yml相同的目录下创建一个包含以下变量的文件：

```env
# GitHub Personal Access Token (create one at https://github.com/settings/tokens)
# Required scopes: repo (for private repositories)
# For public repositories, this is optional but recommended
GITHUB_TOKEN=your_github_token

# Gitea Access Token (create one in your Gitea instance under Settings > Applications)
# Required permissions: read:user, write:repository, write:issue
GITEA_TOKEN=your_gitea_token

# Your Gitea instance URL (no trailing slash)
GITEA_URL=https://your-gitea-instance.com

# Secret key for the web UI (OPTIONAL)
# This key is used to secure Flask sessions and flash messages
# If not provided, a random key will be automatically generated at container start
# SECRET_KEY=your_secret_key

# Log retention days (OPTIONAL, defaults to 30 days)
LOG_RETENTION_DAYS=30
```

### 私有仓库的认证

如需镜像私有 GitHub 仓库，必须提供具备相应权限的 GitHub 访问令牌`repo`范围。此令牌用于在创建镜像时与GitHub进行身份验证。

对于公共仓库，GitHub令牌虽为可选，但建议使用以避免请求频率受限问题。

## 用法

### 使用 Docker Compose（推荐方式）

为便于部署，您可使用 Docker Compose：

1. 启动网页用户界面：
```bash
docker-compose up -d
```

2. 运行镜像脚本（一次性执行）：
```bash
docker-compose run --rm mirror
```

3. 为指定仓库运行镜像脚本：
```bash
docker-compose run --rm mirror mirror owner/repo gitea_owner gitea_repo
```

4. 以特定标志运行：
```bash
# Enable mirroring metadata (issues, PRs, labels, milestones, wikis)
docker-compose run --rm mirror mirror --mirror-metadata

# Force recreation of empty repositories (required when an existing repository is empty but not a mirror)
docker-compose run --rm mirror mirror --force-recreate

# Combine flags for a specific repository
docker-compose run --rm mirror mirror owner/repo gitea_owner gitea_repo --mirror-metadata --force-recreate
```

5. 查看日志：
```bash
docker-compose logs -f
```

6. 停止服务：
```bash
docker-compose down
```

### 使用绑定挂载记录日志

默认情况下，日志存储在Docker卷中以优化权限管理。若您更倾向于使用绑定挂载方式（以便直接在主机文件系统中访问日志），可修改`docker-compose.yml`文件：

1. 请将音量配置从：
```yaml
volumes:
  - gitmirror_logs:/app/logs
```

致：
```yaml
volumes:
  - ./logs:/app/logs
```

2. 创建具有正确权限的日志目录：
```bash
mkdir -p logs
chmod 755 logs
```

3. 更新容器用户以匹配主机用户的UID/GID：
```yaml
environment:
  - PUID=$(id -u)
  - PGID=$(id -g)
user: "${PUID}:${PGID}"
```

4. 请尊重原意，保持原有格式，将以下内容改写为简体中文。`volumes`文件底部定义部分的`gitmirror_logs`

此设置将：
- 将日志直接存储在`logs`主机上的目录
- 允许您无需使用Docker命令即可访问日志
- 请确保为容器配置适当的权限以写入日志
- 请保持原有的日志轮转和保留设置

### 直接使用Docker

要直接使用Docker运行应用程序：

1. 构建Docker镜像：
```bash
docker build -t github-gitea-mirror .
```

2. 运行容器：

a. 运行网页用户界面（默认模式）：
   ```bash
   docker run --rm -p 5000:5000 --env-file .env github-gitea-mirror
   ```

b. 以自动发现模式运行镜像脚本：
   ```bash
   docker run --rm --env-file .env github-gitea-mirror mirror
   ```

c. 针对特定仓库运行镜像脚本：
   ```bash
   docker run --rm --env-file .env github-gitea-mirror mirror owner/repo gitea_owner gitea_repo
   ```
   
d. 使用强制重建标志运行（针对空仓库）：
   ```bash
   docker run --rm --env-file .env github-gitea-mirror mirror owner/repo gitea_owner gitea_repo --force-recreate
   ```

3. 为持久存储日志，请挂载一个卷：
   ```bash
   docker run --rm -p 5000:5000 -v ./logs:/app/logs --env-file .env github-gitea-mirror
   ```

### 镜像的工作原理

当你设置镜像仓库时，该脚本会执行多种类型的同步操作：

1. **代码镜像**：利用Gitea内置的拉取镜像功能实现同步：
   - 整个代码库
   - 所有分支与标签
> 注意：此操作在创建镜像仓库时自动完成，Gitea有时需要一定时间来完成首次代码同步
     

2. **镜像发布**：采用自定义代码实现同步：
   - 发布与发布资源
   - 版本说明与元数据
   - 请尊重原文含义，保持原有格式，并以简体中文重新表述以下内容：

发布附件时需正确命名并添加描述

3. **元数据镜像**：同步额外的GitHub数据：
   - 问题及其评论
   - 拉取请求及其评论
   - 标签与里程碑
   - 维基内容（如启用）

该流程运作如下：

1. 脚本会检查仓库是否存在于Gitea中
2. 若其存在且已为镜像：
   - 触发代码同步
   - 仅当存储库配置中明确启用了相关选项时，才会同步发布版本和元数据
3. 若其存在但非镜像：
   - 若目标仓库为空，需通过明确确认方可继续操作。`--force-recreate`在执行CLI命令（见下文）时使用的标志，在删除并重建为镜像之前
   - 若目标仓库已有提交记录，系统将提示您需手动删除
4. 如果不存在，则创建一个新的仓库作为镜像
5. 配置镜像后，会触发Gitea中的代码同步
6. 仅当仓库配置中启用了相应选项时，才会同步发布版本、议题、拉取请求及其他元数据

默认情况下，所有镜像选项（元数据、发布版本等）均出于安全考虑处于禁用状态。您可通过网页界面的仓库配置页面或使用相应的命令行参数来启用这些功能。

### 仓库安全

该工具内置了防止意外数据丢失的安全防护措施：

1. **空仓库保护**：当现有仓库为空且未配置为镜像时，工具不会自动删除并重新创建，需通过明确确认方可执行此操作。`--force-recreate`旗帜。

2. **非空仓库保护**：若仓库中包含提交记录，工具将始终不会尝试删除该仓库，即便启用`--force-recreate`flag. 这确保了含有实际内容的仓库不会被意外删除。

3. **明确确认**：该`--force-recreate`该标志明确表示您希望删除并重新创建空仓库作为镜像，为意外数据丢失提供了额外的安全防护。

4. **仅限命令行操作**：该`--force-recreate`该标志特意设计为仅可通过命令行界面获取，而非网页用户界面。这一设计选择旨在防止因网页界面误点击而意外删除仓库，确保仓库重建是一个需要特定命令知识的、经过深思熟虑的明确操作。

这种多层次的安全防护机制确保了代码仓库免遭意外删除，同时仍能在必要时灵活地重建空仓库。

### 维基镜像

当镜像一个含有Wiki的GitHub仓库时，工具会为Wiki内容创建一个独立的仓库。这一操作的必要性在于：

1. **Gitea 的局限性**：Gitea 的仓库镜像功能无法自动镜像 Wiki 仓库。Git 中的 Wiki 实质上是独立的仓库（以`.wiki.git`后缀）

2. **只读限制**：对于Gitea中的镜像仓库，其维基部分为只读状态，无法直接推送内容，因此无法直接同步维基内容。

维基内容的镜像流程如下：

1. 该工具会检查GitHub仓库是否含有wiki
2. 它验证了容器中已安装git（此过程为自动完成）
3. 若存在维基，它将克隆GitHub的维基仓库
4. 在Gitea中创建一个名为`{original-repo-name}-wiki`
5. 它将维基内容推送至这一新仓库
6. 它更新了主仓库的描述，以包含指向wiki仓库的链接

该方法确保所有来自GitHub的wiki内容都能在Gitea中保留并访问，即使是镜像仓库也不例外。

### 网页用户界面

网页界面提供了友好的用户界面，便于管理镜像和查看日志：

1. 通过访问网页界面来进入`http://localhost:5000`在启动Docker容器后，请在你的浏览器中访问

2. 使用网页界面进行以下操作：
   - 以列表或卡片视图查看镜像仓库
   - 手动运行镜像
   - 自动刷新查看日志（每5秒更新一次）
   - 配置可自定义间隔的定时镜像任务
   - 配置仓库特定的镜像选项

3. UI特点：
   - 暗色模式支持
   - 配置选项的复选框
   - 错误信息中的日志直接链接
   - 颜色编码状态指示器
   - 响应式设计适配移动端与桌面端

#### 仓库列表视图

![Repository List View](images/repos.png)

#### 添加存储库

![Adding a Repository](images/add-repo.png)

#### 仓库配置

![Repository Configuration](images/repo-config.png)

#### 日志查看器

![Log Viewer](images/logs.png)

### 仓库配置

每个仓库均可单独配置以下选项：

1. **镜像元数据**：启用/禁用元数据（问题、拉取请求、标签等）的镜像功能。
   - 镜像问题：将 GitHub 问题同步至 Gitea
   - 镜像拉取请求：将 GitHub 的 PR 同步至 Gitea
   - 镜像标签：将GitHub标签同步至Gitea
   - 镜中里程碑：将GitHub里程碑同步至Gitea
   - 镜像维基：将GitHub维基同步至独立的Gitea仓库

2. **镜像发布**：开启/关闭将GitHub发布版本镜像至Gitea的功能

这些选项可通过仓库配置页面进行设置，在仓库列表中点击相应仓库的“配置”按钮即可进入。

### 错误处理与日志记录

该应用提供全面的日志记录与错误处理功能：

1. **日志文件**：所有镜像操作均记录在按日期命名的日志文件中。`logs`目录
2. **错误可见性**：错误和警告信息在用户界面中以醒目的颜色编码突出显示
3. **直接日志链接**：错误消息可点击，直接跳转至相关日志文件
4. **状态指示器**：在列表和卡片视图中，存在错误或警告的仓库会以醒目的方式突出显示

镜像过程中出现错误时，可点击错误信息查看详细日志，便于问题诊断与解决。

## 日志

日志存储在`logs`目录中的文件包括：
- 每日午夜轮换
- 保留可配置的天数（默认为30天）
- 按服务分离（网页与镜像）
- 可通过网页界面查看

日志文件遵循以下命名规范：
- 当前日志文件：`web.log`或`mirror.log`
- 轮转日志文件：`web.log.2024-03-20`, `web.log.2024-03-19`等。

日志保留期限可通过配置进行设置`LOG_RETENTION_DAYS`环境变量在您的`.env`文件。

## 开发与测试

### 开发环境配置

1. 安装测试依赖项：
   ```bash
   pip install -r test-requirements.txt
   ```

2. 运行所有测试
   ```bash
   ./run-tests.sh
   ```

3. 运行特定测试类别：
   ```bash
   # Run unit tests
   python -m pytest tests/unit -v
   
   # Run integration tests
   python -m pytest tests/integration -v
   
   # Run with coverage report
   python -m pytest --cov=gitmirror --cov-report=term-missing
   ```

### 测试套件结构

测试套件分为以下几类：

1. **单元测试**`tests/unit/`): 对单个组件进行独立测试
   - `test_github_api.py`测试GitHub API功能
   - `test_gitea_repository.py`测试Gitea仓库操作
   - `test_gitea_api.py`测试Gitea API功能
   - `test_cli.py`测试命令行界面
   - `test_mirror.py`测试核心镜像功能
   - `test_web.py`测试网页界面的路由和功能
   - `test_imports_and_modules.py`: 测试模块导入与基础功能

2. **集成测试**`tests/integration/`测试组件之间的交互
   - `test_mirror_integration.py`测试镜像组件的集成

3. **配置测试**`tests/test_config.py`测试配置的加载与保存

### 测试覆盖率

所有测试均已通过。当前测试覆盖率为27%，主要集中在核心功能部分：

- GitHub API模块：覆盖率86%
- CLI模块：覆盖率84%
- Gitea 仓库模块：测试覆盖率达58%
- 配置工具：覆盖率54%
- 问题模块：覆盖率达42%
- 元数据模块：覆盖率32%

覆盖较低的区域包括：
- 网页界面：覆盖率16%
- PR模块：2%覆盖率
- 评论区模块：覆盖率24%
- Wiki模块：11%覆盖率

### 模拟策略

测试采用大量模拟手段以避免外部依赖：

1. **API请求**：所有HTTP请求均通过模拟方式实现`unittest.mock.patch`为避免实际API调用
2. **文件系统**：文件操作采用模拟方式或使用临时目录
3. **环境变量**：环境变量被模拟以提供测试值
4. **配置**：配置的加载和保存被模拟化，以避免对文件系统的依赖

### 在Docker中运行测试

你也可以在 Docker 容器内运行测试：

```bash
docker-compose run --rm web python -m pytest
```

这确保测试在与生产相似的环境中运行。

## 代码结构

代码库已构建为模块化包以提升可维护性：

- `gitmirror/`主包
  - `github/`GitHub API 交互
  - `gitea/`Gitea API交互，按功能模块组织：
    - `repository.py`仓库管理功能
    - `release.py`：发布管理功能
    - `issue.py`问题管理功能
    - `pr.py`拉取请求管理功能
    - `comment.py`: 评论管理功能
    - `wiki.py`维基管理功能
    - `metadata.py`标签、里程碑及其他元数据功能
  - `utils/`实用功能
    - `logging.py`日志设置与工具，包含日志文件管理
    - `config.py`配置管理工具
  - `mirror.py`: 主镜像逻辑
  - `cli.py`命令行界面
  - `web.py`网页用户界面

这种模块化组织提高了代码的可维护性，便于定位特定功能，同时有利于更集中的测试与开发。

## 许可证

本项目遵循 MIT 许可证 - 详情请参阅 LICENSE 文件。

## 已知限制

- **大型仓库**：包含大量问题、拉取请求或版本的超大型仓库在初次镜像时可能需要较长时间。
- **速率限制**：GitHub API的访问频率限制可能影响频繁更新或大型仓库的镜像性能。
- **认证**：该应用目前仅支持个人访问令牌认证方式。
- **Webhooks**：该工具目前不支持通过webhooks自动同步，而是采用定时同步的方式。
- **双向同步**：这是从 GitHub 到 Gitea 的单向镜像；Gitea 中的更改不会同步回 GitHub。

## 贡献

欢迎贡献！如果您想为此项目贡献力量：

1. 克隆该仓库
2. 创建特性分支`git checkout -b feature/amazing-feature`)
3. 提交您的更改`git commit -m 'Add some amazing feature'`)
4. 推送到分支`git push origin feature/amazing-feature`)
5. 发起拉取请求

请确保在更新测试时保持原有含义，维持原始格式，并遵循现有代码风格。