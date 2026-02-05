import subprocess
import os

# --- 配置 ---
BATCH_SIZE = 500  # 每次提交的文件数量
COMMIT_MSG_PREFIX = "Auto-batch commit: Part"

def run_git_command(args):
    """运行 Git 命令并返回结果"""
    try:
        # 使用 check=True 可以在失败时抛出异常
        result = subprocess.run(args, capture_output=True, text=False, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {' '.join(args)}")
        print(f"错误信息: {e.stderr.decode('utf-8', errors='ignore')}")
        return None

def get_changed_files():
    """使用 -z 参数安全地获取所有变动文件列表"""
    # -z 使用 NUL 字符分隔，避免路径转义和空格问题
    stdout = run_git_command(["git", "status", "--porcelain", "-z"])
    if not stdout:
        return []
    
    files = []
    # 按照 \0 分隔
    entries = stdout.split(b'\x00')
    for entry in entries:
        if not entry:
            continue
        # entry 的前两个字节是状态码（如 M , A , ??），第三个字节是空格
        # 路径从第四个字节（索引 3）开始
        file_path = entry[3:].decode('utf-8', errors='ignore')
        if file_path:
            files.append(file_path)
    return files

def main():
    print("正在获取变更文件列表 (使用安全模式)...")
    all_files = get_changed_files()
    total_files = len(all_files)
    
    if total_files == 0:
        print("没有发现需要提交的文件。")
        return

    print(f"共发现 {total_files} 个文件。开始分批处理...")

    num_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(num_batches):
        start_index = i * BATCH_SIZE
        end_index = min(start_index + BATCH_SIZE, total_files)
        batch_files = all_files[start_index:end_index]
        
        print(f"\n--- 进度: {i+1}/{num_batches} (当前批次: {len(batch_files)} 个文件) ---")
        
        # 使用临时文件来传递路径，防止命令行过长
        list_file = "temp_batch_list.txt"
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                for path in batch_files:
                    f.write(path + "\n")
            
            # 1. git add
            # --pathspec-from-file 是处理大量文件最安全的方式
            subprocess.run(["git", "add", "--pathspec-from-file=" + list_file], check=True)
            
            # 2. git commit
            msg = f"{COMMIT_MSG_PREFIX} {i+1} of {num_batches}"
            subprocess.run(["git", "commit", "-m", msg], check=True)
            
            # 3. git push
            print(f"正在推送第 {i+1} 批次...")
            # 建议在这里捕获 push 错误，因为 push 失败通常是网络问题，可以重试
            push_res = subprocess.run(["git", "push"])
            if push_res.returncode != 0:
                print(f"\n[!] 第 {i+1} 批次推送失败。")
                print("这通常是网络超时。建议停下来，检查网络后手动输入 'git push'。")
                print("由于 Commit 已经成功，你可以稍后一次性 push 所有已提交的批次。")
                break # 停止脚本，防止积压更多 commit
                
        except Exception as e:
            print(f"处理批次时发生异常: {e}")
            break
        finally:
            if os.path.exists(list_file):
                os.remove(list_file)

    print("\n脚本执行结束。")

if __name__ == "__main__":
    main()