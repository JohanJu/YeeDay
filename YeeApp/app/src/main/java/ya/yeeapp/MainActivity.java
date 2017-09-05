package ya.yeeapp;

import android.os.StrictMode;
import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.util.Log;
import android.view.View;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;

public class MainActivity extends AppCompatActivity {


    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        StrictMode.ThreadPolicy policy = new StrictMode.ThreadPolicy.Builder().permitAll().build();
        StrictMode.setThreadPolicy(policy);
    }
    public void on_off(View view) {
        Log.e("test", "on_off");
        try{
            DatagramSocket s = new DatagramSocket();
            byte[] buf = "t".getBytes();
            InetAddress a = InetAddress.getByName("192.168.0.4");
            DatagramPacket p = new DatagramPacket(buf, buf.length, a, 23232);
            s.send(p);
            Log.e("test", "connected");
            s.close();
        }catch(Exception e){
            Log.e("test", "err", e);
        }
    }
}

