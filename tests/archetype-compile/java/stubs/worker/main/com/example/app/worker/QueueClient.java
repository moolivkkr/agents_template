package com.example.app.worker;

import com.example.app.worker.model.Job;

import java.time.Duration;

// Harness stub: an application type the archetype samples use but no archetype defines.
public interface QueueClient {
    Job receive(Duration wait) throws InterruptedException;
    void ack(Job job);
    void nack(Job job, Duration delay);
    void sendToDlq(Job job, String reason);
    boolean isConnected();
}
