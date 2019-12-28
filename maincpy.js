express=require('express');
fs=require('fs');
app=express();
bodyparser=require("body-parser");

app.use(bodyparser.urlencoded({extended:false}));

myModule=require('./myModule');




app.get("/",function(req,resp){

resp.sendFile("calculator.html",{root:__dirname});
console.log("form is shown");
});

app.post("/calculate",function(req,resp){

switch(req.body.operate){

case 'add':
   result= myModule.addition(req.body.num1,req.body.num2);
   resp.send("Addition="+result);
   break;
   
   case 'sub':
   result= myModule.subtract(req.body.num1,req.body.num2);
   resp.send("subtract="+result);
   break;
   case 'mul':
        result=myModule.multiply(req.body.num1,req.body.num2);
        resp.send("Multiplication ="+result);
        break;
 case 'div':
        if(req.body.num2==0)resp.send("Invalid parameter");
        else
        {
            result=myModule.division(req.body.num1,req.body.num2);
            resp.send("Division ="+result);
           
        }  break;
    
    case 'fact':
        result=myModule.factorial(req.body.num1);
        resp.send("Factorial of "+req.body.num1+ "="+result);
        break;
        default:
            resp.send("Bad request");
            break;
    

}

});





app.listen(3000,function(){

    console.log("server is running at port 3000");
});