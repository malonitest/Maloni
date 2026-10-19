#pragma once
#include <chrono>
#include <iostream>
#include <mutex>
#include <string>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

// Poll from the FSM thread; policy reads are protected by the same mutex.
class Keyboard {
public:
  Keyboard() {
    valid_ = isatty(STDIN_FILENO) && tcgetattr(STDIN_FILENO, &original_) == 0;
    if (valid_) {
      auto settings = original_;
      settings.c_lflag &= ~(ICANON | ECHO);
      settings.c_cc[VMIN] = 0;
      settings.c_cc[VTIME] = 0;
      tcsetattr(STDIN_FILENO, TCSANOW, &settings);
    }
  }
  ~Keyboard() { if (valid_) tcsetattr(STDIN_FILENO, TCSANOW, &original_); }
  void update() {
    std::lock_guard<std::mutex> lock(mutex_);
    std::string previous = key_;
    if (valid_) {
      fd_set fds;
      FD_ZERO(&fds); FD_SET(STDIN_FILENO, &fds);
      timeval timeout{0, 0};
      while (select(STDIN_FILENO + 1, &fds, nullptr, nullptr, &timeout) > 0) {
        char c;
        if (read(STDIN_FILENO, &c, 1) != 1) break;
        // Recognize arrow escape sequences without blocking on an isolated Escape.
        if (c == '\033') escape_ = 1;
        else if (escape_ == 1 && c == '[') escape_ = 2;
        else {
          if (escape_ == 2) {
            key_ = c == 'A' ? "up" : c == 'B' ? "down" : c == 'C' ? "right" : c == 'D' ? "left" : "";
          } else key_ = std::string(1, c);
          escape_ = 0;
          last_input_ = std::chrono::steady_clock::now();
        }
        FD_ZERO(&fds); FD_SET(STDIN_FILENO, &fds); timeout = {0, 0};
      }
    }
    // Terminal input has no release events; expire commands after key repeat stops.
    if (std::chrono::steady_clock::now() - last_input_ > std::chrono::milliseconds(600)) {
      key_.clear(); escape_ = 0;
    }
    on_pressed = !key_.empty() && key_ != previous;
    on_released = key_.empty() && !previous.empty();
  }
  std::string key() const { std::lock_guard<std::mutex> lock(mutex_); return key_; }
  std::string getString(std::string slogan) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (valid_) tcsetattr(STDIN_FILENO, TCSANOW, &original_);
    std::cout << slogan << std::endl;
    std::string result; std::getline(std::cin, result);
    if (valid_) {
      auto settings = original_; settings.c_lflag &= ~(ICANON | ECHO);
      settings.c_cc[VMIN] = 0; settings.c_cc[VTIME] = 0;
      tcsetattr(STDIN_FILENO, TCSANOW, &settings);
    }
    return result;
  }
  bool on_pressed = false, on_released = false;
private:
  bool valid_ = false;
  int escape_ = 0;
  termios original_{};
  mutable std::mutex mutex_;
  std::string key_;
  std::chrono::steady_clock::time_point last_input_{};
};
