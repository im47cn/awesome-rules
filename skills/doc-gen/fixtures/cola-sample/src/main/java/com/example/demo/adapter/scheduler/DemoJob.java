package com.example.demo.adapter.scheduler;

import com.xxl.job.core.handler.annotation.XxlJob;
import org.springframework.scheduling.annotation.Scheduled;

public class DemoJob {

    @XxlJob("demoSyncJob")
    public void syncDemo() {
    }

    @Scheduled(cron = "0 0 2 * * ?")
    public void cleanupDemo() {
    }
}
